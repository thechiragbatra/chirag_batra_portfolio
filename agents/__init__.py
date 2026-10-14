"""DeploySmith agents: real and mock implementations behind the `Agent` protocol."""

import os

from agents.base import Agent, AgentUpdate, LogFn
from agents.healer import MockHealer, RealHealer
from agents.profiler import MockProfiler, RealProfiler
from agents.provisioner import MockProvisioner, SandboxProvisioner
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
    "SandboxProvisioner",
    "default_agents",
]


def default_agents() -> list[Agent]:
    """The agents wired into the graph, in pipeline order.

    SANDBOX_ENGINE=1: every agent is real and apps are built and served locally
    in Docker (agents/sandbox/). Otherwise the profiler and strategist are real
    and the provisioner is a mock; the real healer is then opt-in (REAL_HEALER=1)
    because probing made-up URLs would always fail. MOCK_AGENTS=1 swaps
    everything for mocks (offline dev, tests).
    """
    if _flag("MOCK_AGENTS"):
        return [MockProfiler(), MockStrategist(), MockProvisioner(), MockHealer.from_env()]
    if _flag("SANDBOX_ENGINE"):
        return [RealProfiler(), RuleStrategist(sandbox=True), SandboxProvisioner(), RealHealer()]
    healer: Agent = RealHealer() if _flag("REAL_HEALER") else MockHealer.from_env()
    return [RealProfiler(), RuleStrategist(), MockProvisioner(), healer]


def _flag(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes"}
