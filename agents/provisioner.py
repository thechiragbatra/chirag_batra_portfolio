"""Provisioner: creates the planned resources and deploys each component.

Mock: pretends to deploy and returns plausible URLs. On a repair run (after the
healer requested one) it logs that it is applying the fix before redeploying.
Sandbox: re-clones the repo and hands each component to the local engine
(agents/sandbox/engine.py), which builds and serves it in Docker.
"""

from __future__ import annotations

from typing import Literal

from agents.base import AgentUpdate, LogFn, mock_pause
from agents.models import (
    AgentName,
    DeploymentPlan,
    DeploymentResult,
    DeploymentState,
    DeploymentTarget,
    LogLevel,
    Platform,
)
from agents.sandbox.docker import SandboxError
from agents.sandbox.engine import DeployError, Engine
from agents.sandbox.recipes import UnsupportedComponent
from agents.skills.clone import shallow_clone

_URL_TEMPLATE: dict[Platform, str] = {
    Platform.vercel: "https://{slug}.vercel.app",
    Platform.netlify: "https://{slug}.netlify.app",
    Platform.cloudflare_pages: "https://{slug}.pages.dev",
    Platform.render: "https://{slug}-api.onrender.com",
    Platform.hf_spaces: "https://{slug}.hf.space",
    Platform.neon: "postgres://***@ep-{slug}.neon.tech/main",
    Platform.supabase: "postgres://***@db.{slug}.supabase.co/postgres",
    Platform.turso: "libsql://{slug}.turso.io",
    Platform.sandbox: "http://{slug}.localhost:8080",
}


class MockProvisioner:
    name = AgentName.provisioner

    async def run(self, state: DeploymentState, log: LogFn) -> AgentUpdate:
        plan: DeploymentPlan | None = state.deployment_plan
        if plan is None:
            raise ValueError("provisioner requires a deployment_plan")

        attempt = state.repair_attempts
        if attempt > 0 and state.health_report and state.health_report.diagnosis:
            await log(f"Repair attempt {attempt}: {state.health_report.diagnosis}", LogLevel.warn)
            await mock_pause(0.5)

        slug = state.repo_url.rstrip("/").removesuffix(".git").split("/")[-1].lower()
        results: list[DeploymentResult] = []
        for target in plan.targets:
            await log(f"Deploying {target.component} to {target.platform.value}")
            await mock_pause()
            url = _URL_TEMPLATE[target.platform].format(slug=slug)
            results.append(
                DeploymentResult(
                    component=target.component,
                    platform=target.platform,
                    status="live",
                    url=url,
                    attempt=attempt,
                )
            )
            await log(f"{target.component} live at {url}")

        await log(f"Provisioned {len(results)} resources", LogLevel.success)
        return {"deployment_results": results}


class SandboxProvisioner:
    """Deploys every sandbox target with the local engine. Nothing leaves the machine."""

    name = AgentName.provisioner

    def __init__(self, engine: Engine | None = None) -> None:
        self._engine = engine

    @property
    def engine(self) -> Engine:
        if self._engine is None:
            self._engine = Engine()
        return self._engine

    async def run(self, state: DeploymentState, log: LogFn) -> AgentUpdate:
        plan, profile = state.deployment_plan, state.repo_profile
        if plan is None or profile is None:
            raise ValueError("sandbox provisioner requires a repo_profile and a deployment_plan")
        foreign = [t.component for t in plan.targets if t.platform is not Platform.sandbox]
        if foreign:
            raise ValueError(f"sandbox provisioner cannot deploy to other platforms: {foreign}")

        components = {c.name: c for c in profile.components}
        previous = {r.component: r for r in state.deployment_results}
        attempt = state.repair_attempts
        report = state.health_report
        healthy = {c.component for c in report.checks if c.ok} if report else set()
        if attempt > 0 and report and report.diagnosis:
            await log(f"Repair attempt {attempt}: {report.diagnosis}", LogLevel.warn)

        # On a repair only the unhealthy components are redeployed. The source has not
        # changed, so a component whose build failed would fail the same way again.
        results: dict[str, DeploymentResult] = {}
        pending: list[DeploymentTarget] = []
        for target in plan.targets:
            last = previous.get(target.component)
            if attempt > 0 and last is not None and last.status == "failed":
                await log(
                    f"{target.component}: build failed last attempt; not rebuilding", LogLevel.warn
                )
                results[target.component] = last.model_copy(update={"attempt": attempt})
            elif attempt > 0 and last is not None and target.component in healthy:
                await log(f"{target.component}: healthy; keeping {last.url}")
                results[target.component] = last.model_copy(update={"attempt": attempt})
            else:
                pending.append(target)

        single = len(plan.targets) == 1
        if pending:
            async with shallow_clone(state.repo_url) as checkout:
                for target in pending:
                    name = target.component
                    try:
                        _, url = await self.engine.deploy(
                            checkout, state.repo_url, profile.name, components[name], single, log
                        )
                    except (DeployError, UnsupportedComponent, SandboxError) as exc:
                        await log(f"{name}: {exc}", LogLevel.error)
                        results[name] = _result(target, attempt, "failed")
                    else:
                        results[name] = _result(target, attempt, "live", url)

        ordered = [results[t.component] for t in plan.targets]
        live = sum(r.status == "live" for r in ordered)
        level = LogLevel.success if live == len(ordered) else LogLevel.warn
        await log(f"{live}/{len(ordered)} components live in the sandbox", level)
        return {"deployment_results": ordered}


def _result(
    target: DeploymentTarget,
    attempt: int,
    status: Literal["live", "failed"],
    url: str | None = None,
) -> DeploymentResult:
    return DeploymentResult(
        component=target.component,
        platform=target.platform,
        status=status,
        url=url,
        attempt=attempt,
    )
