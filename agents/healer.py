"""Healer: health-checks the deployment and diagnoses failures.

Mock: reports unhealthy for the first `failures_before_healthy` checks, then
healthy. Real: probes every deployed URL over HTTPS (agents/skills/probe.py) and
explains failures with platform-specific rules (agents/skills/diagnose.py).
Whether to retry is the graph's decision, not the healer's.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable

from agents.base import AgentUpdate, LogFn, mock_pause
from agents.models import (
    AgentName,
    DeploymentResult,
    DeploymentState,
    HealthCheck,
    HealthReport,
    LogLevel,
    Platform,
)
from agents.skills.diagnose import is_cold_start, judge
from agents.skills.probe import ProbeResult, probe

ProbeFn = Callable[[str, float], ProbeResult]
SleepFn = Callable[[float], Awaitable[None]]

DATABASE_PLATFORMS = frozenset({Platform.neon, Platform.supabase, Platform.turso})


class MockHealer:
    name = AgentName.healer

    def __init__(self, failures_before_healthy: int = 1) -> None:
        self.failures_before_healthy = failures_before_healthy

    @classmethod
    def from_env(cls) -> MockHealer:
        return cls(int(os.getenv("MOCK_HEALER_FAILURES", "1")))

    @staticmethod
    def _flaky_component(state: DeploymentState) -> str | None:
        """The component the mock pretends is broken: the first backend, else the first result."""
        if state.repo_profile:
            for component in state.repo_profile.components:
                if component.kind == "backend":
                    return component.name
        return state.deployment_results[0].component if state.deployment_results else None

    async def run(self, state: DeploymentState, log: LogFn) -> AgentUpdate:
        healthy = state.repair_attempts >= self.failures_before_healthy
        flaky = self._flaky_component(state)
        checks: list[HealthCheck] = []
        for result in state.deployment_results:
            await log(f"Probing {result.component} ({result.platform.value})")
            await mock_pause(0.5)
            failing = not healthy and result.component == flaky
            checks.append(
                HealthCheck(
                    component=result.component,
                    url=result.url,
                    ok=not failing,
                    status_code=502 if failing else 200,
                    latency_ms=1840 if failing else 120,
                    detail="Bad gateway: app did not bind to $PORT" if failing else "OK",
                )
            )
            if failing:
                await log(f"{result.component} returned 502 Bad Gateway", LogLevel.error)

        if healthy:
            await log("All health checks passed", LogLevel.success)
            return {"health_report": HealthReport(healthy=True, checks=checks)}

        diagnosis = f"{flaky} start command ignores $PORT; bind the server to 0.0.0.0:$PORT"
        await log(f"Diagnosis: {diagnosis}", LogLevel.warn)
        return {"health_report": HealthReport(healthy=False, checks=checks, diagnosis=diagnosis)}


class RealHealer:
    """Probes each deployed component and reports which ones are unhealthy and why.

    Database results are not probed (they are not HTTP endpoints). A component on a
    free tier that sleeps when idle (Render, HF Spaces) gets one slower retry before
    it counts as down, so a cold start is not mistaken for a broken deploy.
    """

    name = AgentName.healer

    def __init__(
        self,
        probe_fn: ProbeFn = probe,
        timeout: float = 15.0,
        cold_start_timeout: float = 60.0,
        cold_start_wait: float = 5.0,
        sleep: SleepFn = asyncio.sleep,
    ) -> None:
        self.probe_fn = probe_fn
        self.timeout = timeout
        self.cold_start_timeout = cold_start_timeout
        self.cold_start_wait = cold_start_wait
        self.sleep = sleep

    async def _probe(self, url: str, timeout: float) -> ProbeResult:
        return await asyncio.to_thread(self.probe_fn, url, timeout)

    async def _check(
        self, result: DeploymentResult, state: DeploymentState, log: LogFn
    ) -> tuple[HealthCheck, str | None]:
        component, platform = result.component, result.platform

        if platform in DATABASE_PLATFORMS:
            await log(f"Skipping {component} ({platform.value}): databases are not probed")
            return HealthCheck(
                component=component, ok=True, detail="Skipped: database, not an HTTP endpoint"
            ), None

        if result.status == "failed" or not result.url:
            await log(f"{component} has no live deployment to probe", LogLevel.error)
            diagnosis = f"{component} on {platform.value}: the provisioner did not deploy it"
            return HealthCheck(
                component=component, url=result.url, ok=False, detail="Not deployed"
            ), diagnosis

        await log(f"Probing {component} at {result.url}")
        outcome = await self._probe(result.url, self.timeout)
        if is_cold_start(platform, outcome):
            await log(
                f"{component} may be waking from free-tier sleep; retrying with a longer timeout",
                LogLevel.warn,
            )
            await self.sleep(self.cold_start_wait)
            outcome = await self._probe(result.url, self.cold_start_timeout)

        kind = _component_kind(state, component)
        verdict = judge(component, kind, platform, outcome, _env_vars(state, component))
        check = HealthCheck(
            component=component,
            url=result.url,
            ok=verdict.ok,
            status_code=outcome.status_code,
            latency_ms=outcome.latency_ms,
            detail=verdict.detail,
        )
        if verdict.ok:
            await log(f"{component} healthy ({verdict.detail}, {outcome.latency_ms} ms)")
        else:
            await log(f"{component} unhealthy: {verdict.detail}", LogLevel.error)
        return check, verdict.diagnosis

    async def run(self, state: DeploymentState, log: LogFn) -> AgentUpdate:
        if not state.deployment_results:
            raise ValueError("healer requires deployment_results")

        checks: list[HealthCheck] = []
        diagnoses: list[str] = []
        for result in state.deployment_results:
            check, diagnosis = await self._check(result, state, log)
            checks.append(check)
            if diagnosis:
                diagnoses.append(diagnosis)

        if not diagnoses:
            await log("All health checks passed", LogLevel.success)
            return {"health_report": HealthReport(healthy=True, checks=checks)}

        diagnosis = "; ".join(diagnoses)
        await log(f"Diagnosis: {diagnosis}", LogLevel.warn)
        return {"health_report": HealthReport(healthy=False, checks=checks, diagnosis=diagnosis)}


def _component_kind(state: DeploymentState, component: str) -> str:
    if state.repo_profile:
        for c in state.repo_profile.components:
            if c.name == component:
                return c.kind
    return "backend"


def _env_vars(state: DeploymentState, component: str) -> list[str]:
    if state.deployment_plan:
        for target in state.deployment_plan.targets:
            if target.component == component:
                return target.env_vars
    return []
