"""DeploySmith agents. Phase 1 ships mock implementations behind the `Agent` protocol."""

import os

from agents.base import Agent, AgentUpdate, LogFn
from agents.healer import MockHealer
from agents.profiler import MockProfiler, RealProfiler
from agents.provisioner import MockProvisioner
from agents.strategist import MockStrategist, RuleStrategist

__all__ = [
    "Agent",
    "AgentUpdate",
    "LogFn",
    "MockHealer",
    "MockProfiler",
    "MockProvisioner",
    "MockStrategist",
    "RealProfiler",
    "RuleStrategist",
    "default_agents",
]


def default_agents() -> list[Agent]:
    """The agents wired into the graph, in pipeline order.

    Profiler and strategist are real; provisioner and healer are still mocks.
    MOCK_AGENTS=1 swaps everything for mocks (offline dev, tests).
    """
    if os.getenv("MOCK_AGENTS", "").lower() in {"1", "true", "yes"}:
        return [MockProfiler(), MockStrategist(), MockProvisioner(), MockHealer.from_env()]
    return [RealProfiler(), RuleStrategist(), MockProvisioner(), MockHealer.from_env()]
