"""Healer: health-checks the deployment and diagnoses failures.

Mock: reports unhealthy for the first `failures_before_healthy` checks, then
healthy. Whether to retry is the graph's decision, not the healer's.
"""

from __future__ import annotations

import os

from agents.base import AgentUpdate, LogFn, mock_pause
from agents.models import AgentName, DeploymentState, HealthCheck, HealthReport, LogLevel


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
