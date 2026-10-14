"""Strategist: maps each profiled component to a free-tier platform.

Mock: applies a fixed component-kind -> platform table. The real version will
weigh build constraints and quotas, but may only choose from `Platform`.
"""

from __future__ import annotations

from agents.base import AgentUpdate, LogFn, mock_pause
from agents.models import (
    AgentName,
    DeploymentPlan,
    DeploymentState,
    DeploymentTarget,
    LogLevel,
    Platform,
)

_DEFAULT_PLATFORM: dict[str, tuple[Platform, str]] = {
    "frontend": (Platform.vercel, "Static Vite build; Vercel Hobby serves it from the edge"),
    "backend": (Platform.render, "Long-running ASGI server fits a Render free web service"),
    "database": (Platform.neon, "Serverless Postgres with a free tier and branching"),
}


class MockStrategist:
    name = AgentName.strategist

    async def run(self, state: DeploymentState, log: LogFn) -> AgentUpdate:
        if state.repo_profile is None:
            raise ValueError("strategist requires a repo_profile")

        await log("Evaluating free-tier platforms for each component")
        await mock_pause()
        targets: list[DeploymentTarget] = []
        for component in state.repo_profile.components:
            platform, reason = _DEFAULT_PLATFORM[component.kind]
            targets.append(
                DeploymentTarget(component=component.name, platform=platform, reason=reason)
            )
            await log(f"{component.name} -> {platform.value}: {reason}")
            await mock_pause(0.4)

        # Wire cross-component env vars: the frontend needs the API URL, the API the DB.
        for target in targets:
            if target.component == "web":
                target.env_vars = ["VITE_API_URL"]
            elif target.component == "api":
                target.env_vars = ["DATABASE_URL"]

        plan = DeploymentPlan(
            targets=targets,
            notes=["Render free services sleep after 15 min idle; first request is slow"],
        )
        await log(f"Plan ready: {len(targets)} targets, all free tier", LogLevel.success)
        return {"deployment_plan": plan}


class RuleStrategist:
    """Deterministic free-tier placement (agents/skills/plan.py). No LLM."""

    name = AgentName.strategist

    async def run(self, state: DeploymentState, log: LogFn) -> AgentUpdate:
        from agents.skills.plan import build_plan

        if state.repo_profile is None:
            raise ValueError("strategist requires a repo_profile")
        await log("Matching each component to a free-tier platform")
        plan = build_plan(state.repo_profile)
        for target in plan.targets:
            await log(f"{target.component} -> {target.platform.value}: {target.reason}")
        for note in plan.notes:
            await log(note, LogLevel.warn)
        await log(f"Plan ready: {len(plan.targets)} targets, all free tier", LogLevel.success)
        return {"deployment_plan": plan}
