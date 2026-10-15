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


async def test_real_profiler_analyzes_cloned_checkout(monkeypatch, tmp_path) -> None:
    from contextlib import asynccontextmanager

    from agents import RealProfiler
    from agents.skills import clone
    from tests.repo_fixtures import VITE_FASTAPI_MONOREPO, write

    repo = write(tmp_path, VITE_FASTAPI_MONOREPO)
    cloned: list[str] = []

    @asynccontextmanager
    async def fake_clone(url: str):
        cloned.append(url)
        yield repo

    monkeypatch.setattr(clone, "shallow_clone", fake_clone)
    logs = Logs()
    profile = (await RealProfiler().run(DeploymentState(repo_url=REPO), logs))["repo_profile"]

    assert cloned == [REPO]
    assert {c.name for c in profile.components} == {"api", "frontend", "db"}
    messages = [m for _, m in logs.lines]
    assert any("nothing executed" in m for m in messages)
    assert any("Detected backend in api/: fastapi" in m for m in messages)
    assert logs.lines[-1][0] is LogLevel.success


async def test_rule_strategist_plans_from_profile(tmp_path) -> None:
    from agents import RuleStrategist
    from agents.skills.analyze import analyze_repo
    from tests.repo_fixtures import VITE_FASTAPI_MONOREPO, write

    state = DeploymentState(repo_url=REPO)
    state.repo_profile = analyze_repo(write(tmp_path, VITE_FASTAPI_MONOREPO), "acme/shop")
    logs = Logs()
    plan = (await RuleStrategist().run(state, logs))["deployment_plan"]
    assert {t.component: t.platform for t in plan.targets} == {
        "api": Platform.render,
        "frontend": Platform.vercel,
        "db": Platform.neon,
    }
    assert any(level is LogLevel.warn for level, _ in logs.lines)  # free-tier caveats


async def test_mock_healer_fails_first_backend_component(tmp_path) -> None:
    from agents.models import Component, DeploymentResult, RepoProfile

    state = DeploymentState(repo_url=REPO)
    state.repo_profile = RepoProfile(
        name="acme/shop", default_branch="main", languages=[], frameworks=[],
        components=[Component(name="site", kind="frontend", path="."),
                    Component(name="server", kind="backend", path="srv")],
    )  # fmt: skip
    state.deployment_results = [
        DeploymentResult(component=n, platform=Platform.render, status="live", attempt=0)
        for n in ("site", "server")
    ]
    report = (await MockHealer(failures_before_healthy=1).run(state, Logs()))["health_report"]
    assert [c.ok for c in report.checks] == [True, False]
    assert report.diagnosis and report.diagnosis.startswith("server ")


def test_default_agents_switch(monkeypatch) -> None:
    from agents import RealProfiler, RuleStrategist, default_agents

    monkeypatch.setenv("MOCK_AGENTS", "0")
    real = default_agents()
    assert isinstance(real[0], RealProfiler) and isinstance(real[1], RuleStrategist)
    monkeypatch.setenv("MOCK_AGENTS", "1")
    assert isinstance(default_agents()[0], MockProfiler)
