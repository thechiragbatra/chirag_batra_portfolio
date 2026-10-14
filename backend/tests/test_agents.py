from agents import MockHealer, MockProfiler, MockProvisioner, MockStrategist
from agents.models import AgentName, DeploymentState, LogLevel, Platform
from agents.profiler import repo_name_from_url

REPO = "https://github.com/acme/shop"


class Logs:
    def __init__(self) -> None:
        self.lines: list[tuple[LogLevel, str]] = []

    async def __call__(self, message: str, level: LogLevel = LogLevel.info) -> None:
        self.lines.append((level, message))


def test_repo_name_from_url() -> None:
    assert repo_name_from_url("https://github.com/acme/shop.git") == "acme/shop"
    assert repo_name_from_url("https://github.com/acme/shop/") == "acme/shop"


async def test_profiler_returns_profile_and_logs() -> None:
    logs = Logs()
    update = await MockProfiler().run(DeploymentState(repo_url=REPO), logs)
    profile = update["repo_profile"]
    assert profile.name == "acme/shop"
    assert {c.kind for c in profile.components} == {"frontend", "backend", "database"}
    assert logs.lines and logs.lines[-1][0] is LogLevel.success


async def test_strategist_plans_free_tier_target_per_component() -> None:
    state = DeploymentState(repo_url=REPO)
    state.repo_profile = (await MockProfiler().run(state, Logs()))["repo_profile"]
    plan = (await MockStrategist().run(state, Logs()))["deployment_plan"]
    assert [t.component for t in plan.targets] == ["web", "api", "db"]
    assert all(isinstance(t.platform, Platform) for t in plan.targets)


async def test_provisioner_deploys_every_target() -> None:
    state = DeploymentState(repo_url=REPO)
    state.repo_profile = (await MockProfiler().run(state, Logs()))["repo_profile"]
    state.deployment_plan = (await MockStrategist().run(state, Logs()))["deployment_plan"]
    results = (await MockProvisioner().run(state, Logs()))["deployment_results"]
    assert len(results) == len(state.deployment_plan.targets)
    assert all(r.url and "shop" in r.url and r.attempt == 0 for r in results)


async def test_healer_fails_then_recovers() -> None:
    state = DeploymentState(repo_url=REPO)
    state.repo_profile = (await MockProfiler().run(state, Logs()))["repo_profile"]
    state.deployment_plan = (await MockStrategist().run(state, Logs()))["deployment_plan"]
    state.deployment_results = (await MockProvisioner().run(state, Logs()))["deployment_results"]
    healer = MockHealer(failures_before_healthy=1)

    first = (await healer.run(state, Logs()))["health_report"]
    assert not first.healthy and first.diagnosis
    state.repair_attempts = 1
    second = (await healer.run(state, Logs()))["health_report"]
    assert second.healthy


def test_healer_from_env(monkeypatch) -> None:
    monkeypatch.setenv("MOCK_HEALER_FAILURES", "4")
    assert MockHealer.from_env().failures_before_healthy == 4
    assert MockHealer.name is AgentName.healer
