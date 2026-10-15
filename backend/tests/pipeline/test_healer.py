"""RealHealer with a scripted probe: no network, no sleeping."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from agents import RealHealer, default_agents
from agents.models import (
    AgentName,
    Component,
    DeploymentPlan,
    DeploymentResult,
    DeploymentState,
    DeploymentTarget,
    LogLevel,
    Platform,
    RepoProfile,
)
from agents.skills.probe import ProbeResult

WEB = "https://shop.vercel.app"
API = "https://shop-api.onrender.com"


class Logs:
    def __init__(self) -> None:
        self.lines: list[tuple[LogLevel, str]] = []

    async def __call__(self, message: str, level: LogLevel = LogLevel.info) -> None:
        self.lines.append((level, message))


class ScriptedProbe:
    """Returns queued responses per URL and records each call's timeout."""

    def __init__(self, responses: dict[str, list[ProbeResult]]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, float]] = []

    def __call__(self, url: str, timeout: float) -> ProbeResult:
        self.calls.append((url, timeout))
        return self.responses[url].pop(0)


async def no_sleep(_: float) -> None:
    return None


def ok(url: str) -> ProbeResult:
    return ProbeResult(url=url, status_code=200, latency_ms=40)


def code(url: str, status: int) -> ProbeResult:
    return ProbeResult(url=url, status_code=status, latency_ms=40)


def deployed_state(*extra: DeploymentResult) -> DeploymentState:
    return DeploymentState(
        repo_url="https://github.com/acme/shop",
        repo_profile=RepoProfile(
            name="acme/shop",
            default_branch="main",
            languages=["TypeScript", "Python"],
            frameworks=["Vite", "FastAPI"],
            components=[
                Component(name="web", kind="frontend", path="web"),
                Component(name="api", kind="backend", path="api"),
                Component(name="db", kind="database", path="api"),
            ],
        ),
        deployment_plan=DeploymentPlan(
            targets=[
                DeploymentTarget(component="web", platform=Platform.vercel, reason="vite"),
                DeploymentTarget(
                    component="api",
                    platform=Platform.render,
                    reason="fastapi",
                    env_vars=["DATABASE_URL"],
                ),
            ]
        ),
        deployment_results=[
            DeploymentResult(
                component="web", platform=Platform.vercel, status="live", url=WEB, attempt=0
            ),
            DeploymentResult(
                component="api", platform=Platform.render, status="live", url=API, attempt=0
            ),
            *extra,
        ],
    )


def healer(probe: Callable[[str, float], ProbeResult]) -> RealHealer:
    return RealHealer(probe_fn=probe, timeout=5, cold_start_timeout=30, sleep=no_sleep)


async def test_all_healthy() -> None:
    probe = ScriptedProbe({WEB: [ok(WEB)], API: [ok(API)]})
    logs = Logs()
    report = (await healer(probe).run(deployed_state(), logs))["health_report"]
    assert report.healthy and report.diagnosis is None
    assert [c.status_code for c in report.checks] == [200, 200]
    assert probe.calls == [(WEB, 5), (API, 5)]
    assert logs.lines[-1] == (LogLevel.success, "All health checks passed")


async def test_unhealthy_backend_is_diagnosed() -> None:
    probe = ScriptedProbe({WEB: [ok(WEB)], API: [code(API, 500)]})
    report = (await healer(probe).run(deployed_state(), Logs()))["health_report"]
    assert not report.healthy
    assert [c.ok for c in report.checks] == [True, False]
    assert report.diagnosis == (
        "api on render: the app raises on startup or on GET /; "
        "confirm these env vars are set: DATABASE_URL"
    )


async def test_cold_start_is_retried_once_with_longer_timeout() -> None:
    probe = ScriptedProbe({WEB: [ok(WEB)], API: [code(API, 503), ok(API)]})
    logs = Logs()
    report = (await healer(probe).run(deployed_state(), logs))["health_report"]
    assert report.healthy
    assert probe.calls == [(WEB, 5), (API, 5), (API, 30)]
    assert any("waking from free-tier sleep" in msg for _, msg in logs.lines)


async def test_cold_start_that_stays_down_is_diagnosed() -> None:
    probe = ScriptedProbe({WEB: [ok(WEB)], API: [code(API, 502), code(API, 502)]})
    report = (await healer(probe).run(deployed_state(), Logs()))["health_report"]
    assert not report.healthy and "0.0.0.0:$PORT" in (report.diagnosis or "")


async def test_vercel_failure_is_not_retried() -> None:
    probe = ScriptedProbe({WEB: [code(WEB, 503)], API: [ok(API)]})
    report = (await healer(probe).run(deployed_state(), Logs()))["health_report"]
    assert not report.healthy
    assert probe.calls == [(WEB, 5), (API, 5)]


async def test_databases_and_failed_deploys_are_not_probed() -> None:
    state = deployed_state(
        DeploymentResult(
            component="db",
            platform=Platform.neon,
            status="live",
            url="postgres://***@ep-shop.neon.tech/main",
            attempt=0,
        ),
        DeploymentResult(component="worker", platform=Platform.render, status="failed", attempt=0),
    )
    probe = ScriptedProbe({WEB: [ok(WEB)], API: [ok(API)]})
    report = (await healer(probe).run(state, Logs()))["health_report"]
    assert [c.component for c in report.checks] == ["web", "api", "db", "worker"]
    assert [c.ok for c in report.checks] == [True, True, True, False]
    assert report.diagnosis == "worker on render: the provisioner did not deploy it"
    assert {url for url, _ in probe.calls} == {WEB, API}


async def test_requires_deployment_results() -> None:
    with pytest.raises(ValueError, match="deployment_results"):
        await healer(ScriptedProbe({})).run(
            DeploymentState(repo_url="https://github.com/a/b"), Logs()
        )


async def test_blocked_url_fails_without_network() -> None:
    """The default probe refuses URLs off the platform domains before connecting."""
    state = deployed_state()
    state.deployment_results[1].url = "https://169.254.169.254/latest/meta-data"
    probe = ScriptedProbe({WEB: [ok(WEB)]})

    def real_for_api(url: str, timeout: float) -> ProbeResult:
        from agents.skills.probe import probe as real_probe

        return probe(url, timeout) if url == WEB else real_probe(url, timeout)

    report = (await healer(real_for_api).run(state, Logs()))["health_report"]
    assert not report.healthy and "not on a free-tier platform domain" in (report.diagnosis or "")


def test_default_agents_healer_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    def healer_type() -> type:
        return type({a.name: a for a in default_agents()}[AgentName.healer])

    monkeypatch.setenv("MOCK_AGENTS", "0")
    monkeypatch.delenv("REAL_HEALER", raising=False)
    assert healer_type().__name__ == "MockHealer"
    monkeypatch.setenv("REAL_HEALER", "1")
    assert healer_type() is RealHealer
    monkeypatch.setenv("MOCK_AGENTS", "1")
    assert healer_type().__name__ == "MockHealer"
