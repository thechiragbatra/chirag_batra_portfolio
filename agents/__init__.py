"""DeploySmith agents: real and mock implementations behind the `Agent` protocol."""

import os

from agents.base import Agent, AgentUpdate, LogFn
from agents.healer import MockHealer, RealHealer
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
    "RealHealer",
    "RealProfiler",
    "RuleStrategist",
    "default_agents",
]


def default_agents() -> list[Agent]:
    """The agents wired into the graph, in pipeline order.

    Profiler and strategist are real; the provisioner is still a mock. The real
    healer is opt-in (REAL_HEALER=1) because probing the mock provisioner's
    made-up URLs would always fail. MOCK_AGENTS=1 swaps everything for mocks.
    """
    if _flag("MOCK_AGENTS"):
        return [MockProfiler(), MockStrategist(), MockProvisioner(), MockHealer.from_env()]
    healer: Agent = RealHealer() if _flag("REAL_HEALER") else MockHealer.from_env()
    return [RealProfiler(), RuleStrategist(), MockProvisioner(), healer]


def _flag(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes"}
