from typing import Any

import pytest

from agents import MockHealer, MockProfiler, MockProvisioner, MockStrategist
from agents.base import AgentUpdate, LogFn
from agents.models import MAX_REPAIR_ATTEMPTS, AgentName, AgentStatus, DeploymentState, Platform
from app.services.events import Event, LogEvent, StatusEvent
from app.services.graph import build_graph, run_deployment

REPO = "https://github.com/acme/shop"


def agents_with(healer: Any = None, **overrides: Any) -> list[Any]:
    return [
        overrides.get("profiler", MockProfiler()),
        overrides.get("strategist", MockStrategist()),
        overrides.get("provisioner", MockProvisioner()),
        healer or MockHealer(failures_before_healthy=0),
    ]


class Recorder:
    def __init__(self) -> None:
        self.events: list[Event] = []

    async def __call__(self, event: Event) -> None:
        self.events.append(event)

    def statuses(self, agent: AgentName) -> list[AgentStatus]:
        return [e.status for e in self.events if isinstance(e, StatusEvent) and e.agent == agent]


class CountingProvisioner(MockProvisioner):
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, state: DeploymentState, log: LogFn) -> AgentUpdate:
        self.calls += 1
        return await super().run(state, log)


async def test_happy_path_runs_every_agent_once() -> None:
    recorder = Recorder()
    state = await run_deployment(build_graph(agents_with()), REPO, recorder)

    assert state.errors == []
    assert state.repair_attempts == 0
    assert state.agent_status == {name: AgentStatus.done for name in AgentName}
    assert state.repo_profile is not None and state.repo_profile.name == "acme/shop"
    assert state.deployment_plan is not None
    assert {t.platform for t in state.deployment_plan.targets} <= set(Platform)
    assert all(r.status == "live" for r in state.deployment_results)
    assert state.health_report is not None and state.health_report.healthy

    for name in AgentName:
        assert recorder.statuses(name) == [AgentStatus.running, AgentStatus.done]
    assert any(isinstance(e, LogEvent) for e in recorder.events)


async def test_single_repair_then_healthy() -> None:
    provisioner = CountingProvisioner()
    state = await run_deployment(
        build_graph(agents_with(MockHealer(failures_before_healthy=1), provisioner=provisioner)),
        REPO,
    )

    assert provisioner.calls == 2
    assert state.repair_attempts == 1
    assert state.health_report is not None and state.health_report.healthy
    assert state.agent_status[AgentName.healer] == AgentStatus.done
    assert state.errors == []


async def test_healer_loop_stops_after_max_repairs() -> None:
    provisioner = CountingProvisioner()
    recorder = Recorder()
    state = await run_deployment(
        build_graph(agents_with(MockHealer(failures_before_healthy=99), provisioner=provisioner)),
        REPO,
        recorder,
    )

    assert MAX_REPAIR_ATTEMPTS == 3
    assert state.repair_attempts == MAX_REPAIR_ATTEMPTS
    assert provisioner.calls == 1 + MAX_REPAIR_ATTEMPTS
    assert state.health_report is not None and not state.health_report.healthy
    assert state.agent_status[AgentName.healer] == AgentStatus.failed
    assert any("3 repair attempts" in error for error in state.errors)
    assert recorder.statuses(AgentName.healer)[-1] == AgentStatus.failed


async def test_agent_exception_fails_run_and_skips_later_agents() -> None:
    class BrokenStrategist(MockStrategist):
        async def run(self, state: DeploymentState, log: LogFn) -> AgentUpdate:
            raise RuntimeError("quota exceeded")

    provisioner = CountingProvisioner()
    recorder = Recorder()
    state = await run_deployment(
        build_graph(agents_with(strategist=BrokenStrategist(), provisioner=provisioner)),
        REPO,
        recorder,
    )

    assert state.agent_status[AgentName.strategist] == AgentStatus.failed
    assert state.agent_status[AgentName.provisioner] == AgentStatus.idle
    assert provisioner.calls == 0
    assert state.errors == ["strategist: quota exceeded"]
    assert recorder.statuses(AgentName.provisioner) == []


def test_build_graph_requires_all_agents() -> None:
    with pytest.raises(ValueError, match="missing agents"):
        build_graph([MockProfiler()])
