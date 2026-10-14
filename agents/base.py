"""The contract every agent implements.

An agent reads the current DeploymentState, reports progress through `log`, and
returns a partial state update. It never touches the event stream, its own
status, or the repair counter: the graph wrapper in backend/graph.py owns those.
Real implementations replace the mocks by satisfying the same Protocol.
"""

from __future__ import annotations

import asyncio
import os
from typing import Protocol, TypedDict

from agents.models import (
    AgentName,
    DeploymentPlan,
    DeploymentResult,
    DeploymentState,
    HealthReport,
    LogLevel,
    RepoProfile,
)

__all__ = ["Agent", "AgentUpdate", "LogFn", "LogLevel", "mock_pause"]


class AgentUpdate(TypedDict, total=False):
    repo_profile: RepoProfile
    deployment_plan: DeploymentPlan
    deployment_results: list[DeploymentResult]
    health_report: HealthReport
    errors: list[str]


class LogFn(Protocol):
    async def __call__(self, message: str, level: LogLevel = LogLevel.info) -> None: ...


class Agent(Protocol):
    name: AgentName

    async def run(self, state: DeploymentState, log: LogFn) -> AgentUpdate: ...


async def mock_pause(scale: float = 1.0) -> None:
    """Simulate work. MOCK_AGENT_DELAY is read per call so tests can set it to 0."""
    delay = float(os.getenv("MOCK_AGENT_DELAY", "0.6")) * scale
    if delay > 0:
        await asyncio.sleep(delay)
