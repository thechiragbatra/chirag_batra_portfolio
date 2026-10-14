"""Provisioner: creates the planned resources and deploys each component.

Mock: pretends to deploy and returns plausible URLs. On a repair run (after the
healer requested one) it logs that it is applying the fix before redeploying.
"""

from __future__ import annotations

from agents.base import AgentUpdate, LogFn, mock_pause
from agents.models import (
    AgentName,
    DeploymentPlan,
    DeploymentResult,
    DeploymentState,
    LogLevel,
    Platform,
)

_URL_TEMPLATE: dict[Platform, str] = {
    Platform.vercel: "https://{slug}.vercel.app",
    Platform.netlify: "https://{slug}.netlify.app",
    Platform.cloudflare_pages: "https://{slug}.pages.dev",
    Platform.render: "https://{slug}-api.onrender.com",
    Platform.hf_spaces: "https://{slug}.hf.space",
    Platform.neon: "postgres://***@ep-{slug}.neon.tech/main",
    Platform.supabase: "postgres://***@db.{slug}.supabase.co/postgres",
    Platform.turso: "libsql://{slug}.turso.io",
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
