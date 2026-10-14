"""DeploySmith agents. Phase 1 ships mock implementations behind the `Agent` protocol."""

from agents.base import Agent, AgentUpdate, LogFn
from agents.healer import MockHealer
from agents.profiler import MockProfiler
from agents.provisioner import MockProvisioner
from agents.strategist import MockStrategist

__all__ = [
    "Agent",
    "AgentUpdate",
    "LogFn",
    "MockHealer",
    "MockProfiler",
    "MockProvisioner",
    "MockStrategist",
    "default_agents",
]


def default_agents() -> list[Agent]:
    """The agents wired into the graph, in pipeline order."""
    return [MockProfiler(), MockStrategist(), MockProvisioner(), MockHealer.from_env()]
