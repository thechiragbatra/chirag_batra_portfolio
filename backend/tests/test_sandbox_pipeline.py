"""The sandbox engine wired into the agents: strategist, provisioner, healer, selection."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from agents import RealHealer, SandboxProvisioner, default_agents
from agents.models import (
    AgentName,
    Component,
    DeploymentPlan,
    DeploymentResult,
    DeploymentState,
    DeploymentTarget,
    HealthCheck,
    HealthReport,
    LogLevel,
    Platform,
    RepoProfile,
)
from agents.sandbox.engine import DeployError
from agents.skills.diagnose import judge
from agents.skills.plan import build_plan
from agents.skills.probe import ProbeResult
from agents.strategist import RuleStrategist


class Logs:
    def __init__(self) -> None:
        self.lines: list[tuple[LogLevel, str]] = []

    async def __call__(self, message: str, level: LogLevel = LogLevel.info) -> None:
        self.lines.append((level, message))


PROFILE = RepoProfile(
    name="acme/shop",
    default_branch="main",
    languages=["TypeScript", "Python"],
    frameworks=["vite", "fastapi", "nuxt"],
    components=[
        Component(
            name="web", kind="frontend", path="web", framework="vite", build_command="npm run build"
        ),
        Component(
            name="api",
            kind="backend",
            path="api",
            framework="fastapi",
            start_command="uvicorn main:app",
        ),
        Component(
            name="docs",
            kind="frontend",
            path="docs",
            framework="nuxt",
            build_command="npm run build",
        ),
        Component(name="db", kind="database", path=".", framework="postgres"),
    ],
    env_vars=["DATABASE_URL", "VITE_API_URL"],
)


def test_sandbox_plan_places_supported_apps_only() -> None:
    plan = build_plan(PROFILE, sandbox=True)
    assert [(t.component, t.platform) for t in plan.targets] == [
        ("web", Platform.sandbox),
        ("api", Platform.sandbox),
    ]
    assert plan.targets[1].env_vars == ["DATABASE_URL"]
    assert any("no recipe for nuxt" in n for n in plan.notes)
    assert any("does not provision databases" in n for n in plan.notes)
    assert any("http://<app>.localhost" in n for n in plan.notes)


def test_sandbox_plan_raises_when_nothing_fits() -> None:
    profile = PROFILE.model_copy(update={"components": PROFILE.components[2:]})
    with pytest.raises(ValueError, match="sandbox engine"):
        build_plan(profile, sandbox=True)


async def test_rule_strategist_sandbox_mode() -> None:
    logs = Logs()
    state = DeploymentState(repo_url="https://github.com/acme/shop", repo_profile=PROFILE)
    plan = (await RuleStrategist(sandbox=True).run(state, logs))["deployment_plan"]
    assert all(t.platform is Platform.sandbox for t in plan.targets)
    assert logs.lines[-1] == (LogLevel.success, "Plan ready: 2 targets, all local")


# --- provisioner --------------------------------------------------------------------


class FakeEngine:
    def __init__(self, fail: set[str] = frozenset()) -> None:  # type: ignore[assignment]
        self.fail = fail
        self.calls: list[tuple[str, bool]] = []

    async def deploy(
        self,
        checkout: Path,
        repo_url: str,
        repo_name: str,
        component: Component,
        single: bool,
        log: Any,
    ) -> tuple[str, str]:
        self.calls.append((component.name, single))
        if component.name in self.fail:
            raise DeployError("`npm run build` exited with code 1")
        return component.name, f"http://shop-{component.name}.localhost:8080"


def sandbox_state(**overrides: Any) -> DeploymentState:
    plan = DeploymentPlan(
        targets=[
            DeploymentTarget(component="web", platform=Platform.sandbox, reason="r"),
            DeploymentTarget(component="api", platform=Platform.sandbox, reason="r"),
        ]
    )
    return DeploymentState(
        repo_url="https://github.com/acme/shop",
        repo_profile=PROFILE,
        deployment_plan=plan,
        **overrides,
    )


@pytest.fixture
def no_clone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    """Stub the clone; returns the list of repo URLs that would have been cloned."""
    clones: list[str] = []

    @asynccontextmanager
    async def fake_clone(repo_url: str, **_: Any):  # type: ignore[no-untyped-def]
        clones.append(repo_url)
        yield tmp_path

    monkeypatch.setattr("agents.provisioner.shallow_clone", fake_clone)
    return clones


async def test_sandbox_provisioner_deploys_each_target(no_clone: None) -> None:
    engine = FakeEngine()
    logs = Logs()
    results = (await SandboxProvisioner(engine).run(sandbox_state(), logs))["deployment_results"]  # type: ignore[arg-type]
    assert engine.calls == [("web", False), ("api", False)]
    assert [(r.component, r.status, r.url) for r in results] == [
        ("web", "live", "http://shop-web.localhost:8080"),
        ("api", "live", "http://shop-api.localhost:8080"),
    ]
    assert logs.lines[-1] == (LogLevel.success, "2/2 components live in the sandbox")


async def test_sandbox_provisioner_records_failures_and_continues(no_clone: None) -> None:
    engine = FakeEngine(fail={"web"})
    logs = Logs()
    results = (await SandboxProvisioner(engine).run(sandbox_state(), logs))["deployment_results"]  # type: ignore[arg-type]
    assert [(r.component, r.status) for r in results] == [("web", "failed"), ("api", "live")]
    assert (LogLevel.error, "web: `npm run build` exited with code 1") in logs.lines
    assert logs.lines[-1][0] is LogLevel.warn


async def test_sandbox_provisioner_does_not_rebuild_failed_source_on_repair(no_clone: None) -> None:
    engine = FakeEngine()
    previous = [
        DeploymentResult(component="web", platform=Platform.sandbox, status="failed", attempt=0),
        DeploymentResult(
            component="api",
            platform=Platform.sandbox,
            status="live",
            url="http://shop-api.localhost:8080",
            attempt=0,
        ),
    ]
    state = sandbox_state(
        deployment_results=previous,
        repair_attempts=1,
        health_report=HealthReport(healthy=False, checks=[], diagnosis="web on sandbox: x"),
    )
    results = (await SandboxProvisioner(engine).run(state, Logs()))["deployment_results"]  # type: ignore[arg-type]
    assert engine.calls == [("api", False)]
    assert [(r.component, r.status, r.attempt) for r in results] == [
        ("web", "failed", 1),
        ("api", "live", 1),
    ]


def live(component: str, attempt: int = 0) -> DeploymentResult:
    return DeploymentResult(
        component=component,
        platform=Platform.sandbox,
        status="live",
        url=f"http://shop-{component}.localhost:8080",
        attempt=attempt,
    )


async def test_sandbox_provisioner_redeploys_only_unhealthy_components(
    no_clone: list[str],
) -> None:
    engine = FakeEngine()
    checks = [
        HealthCheck(component="web", url=live("web").url, ok=False, status_code=502, detail="x"),
        HealthCheck(component="api", url=live("api").url, ok=True, status_code=200, detail="ok"),
    ]
    state = sandbox_state(
        deployment_results=[live("web"), live("api")],
        repair_attempts=1,
        health_report=HealthReport(healthy=False, checks=checks, diagnosis="web on sandbox: 502"),
    )
    logs = Logs()
    results = (await SandboxProvisioner(engine).run(state, logs))["deployment_results"]  # type: ignore[arg-type]
    assert engine.calls == [("web", False)]
    assert [(r.component, r.status, r.attempt) for r in results] == [
        ("web", "live", 1),
        ("api", "live", 1),
    ]
    assert (LogLevel.info, "api: healthy; keeping http://shop-api.localhost:8080") in logs.lines
    assert no_clone == ["https://github.com/acme/shop"]


async def test_sandbox_provisioner_skips_clone_when_nothing_to_redeploy(
    no_clone: list[str],
) -> None:
    engine = FakeEngine()
    failed = [
        DeploymentResult(component="web", platform=Platform.sandbox, status="failed", attempt=0),
        DeploymentResult(component="api", platform=Platform.sandbox, status="failed", attempt=0),
    ]
    state = sandbox_state(
        deployment_results=failed,
        repair_attempts=2,
        health_report=HealthReport(healthy=False, checks=[], diagnosis="nothing deployed"),
    )
    results = (await SandboxProvisioner(engine).run(state, Logs()))["deployment_results"]  # type: ignore[arg-type]
    assert engine.calls == [] and no_clone == []
    assert [(r.status, r.attempt) for r in results] == [("failed", 2), ("failed", 2)]


async def test_sandbox_provisioner_rejects_foreign_targets(no_clone: None) -> None:
    state = sandbox_state()
    state.deployment_plan.targets[0].platform = Platform.vercel  # type: ignore[union-attr]
    with pytest.raises(ValueError, match="other platforms"):
        await SandboxProvisioner(FakeEngine()).run(state, Logs())  # type: ignore[arg-type]


# --- healer rules for the sandbox ---------------------------------------------------


def test_sandbox_diagnoses() -> None:
    url = "http://shop.localhost:8080"
    gone = ProbeResult(url=url, status_code=404, body="No app is deployed at this address.\n")
    assert "no live deploy" in (judge("web", "frontend", Platform.sandbox, gone).diagnosis or "")
    down = ProbeResult(url=url, status_code=502)
    assert "0.0.0.0:$PORT" in (judge("api", "backend", Platform.sandbox, down).diagnosis or "")
    refused = ProbeResult(url=url, error="connection", error_detail="refused")
    assert "router is not running" in (
        judge("api", "backend", Platform.sandbox, refused).diagnosis or ""
    )


def test_sandbox_engine_selects_all_real_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MOCK_AGENTS", "0")
    monkeypatch.setenv("SANDBOX_ENGINE", "1")
    agents = {a.name: a for a in default_agents()}
    assert isinstance(agents[AgentName.provisioner], SandboxProvisioner)
    assert isinstance(agents[AgentName.healer], RealHealer)
    assert isinstance(agents[AgentName.strategist], RuleStrategist)
    assert agents[AgentName.strategist].sandbox is True  # type: ignore[attr-defined]
