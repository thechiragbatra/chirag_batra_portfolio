from __future__ import annotations

import pytest

from agents.models import Platform
from agents.skills.diagnose import is_cold_start, judge
from agents.skills.probe import ProbeResult

URL = "https://shop.example"


def status(code: int, body: str = "") -> ProbeResult:
    return ProbeResult(url=URL, status_code=code, latency_ms=50, body=body)


def error(kind: str, detail: str = "") -> ProbeResult:
    return ProbeResult(url=URL, error=kind, error_detail=detail)  # type: ignore[arg-type]


@pytest.mark.parametrize("code", [200, 204, 301, 308])
def test_2xx_and_3xx_are_healthy(code: int) -> None:
    verdict = judge("web", "frontend", Platform.vercel, status(code))
    assert verdict.ok and verdict.diagnosis is None and verdict.detail == f"HTTP {code}"


def test_redirect_to_custom_domain_is_healthy() -> None:
    probe = ProbeResult(url=URL, status_code=308, headers={"location": "https://shop.com/"})
    verdict = judge("web", "frontend", Platform.vercel, probe)
    assert verdict.ok and verdict.detail == "HTTP 308 -> https://shop.com/"


def test_redirect_to_vercel_login_is_protection() -> None:
    login = "https://vercel.com/sso-api?url=https%3A%2F%2Fshop.vercel.app%2F&nonce=1"
    probe = ProbeResult(url=URL, status_code=302, headers={"location": login})
    verdict = judge("web", "frontend", Platform.vercel, probe)
    assert not verdict.ok and verdict.detail == "HTTP 302 -> Vercel login"
    assert verdict.diagnosis and "Deployment Protection" in verdict.diagnosis


@pytest.mark.parametrize(
    "platform, probe, kind, expected",
    [
        (Platform.vercel, status(404), "frontend", "build output directory"),
        (
            Platform.vercel,
            status(404, "The deployment could not be found on Vercel."),
            "frontend",
            "no Vercel deployment",
        ),
        (Platform.netlify, status(404, "Not Found - site not found"), "frontend", "Netlify site"),
        (Platform.render, status(404), "backend", "health route"),
        (Platform.vercel, status(401), "frontend", "Deployment Protection"),
        (Platform.hf_spaces, status(403), "backend", "private"),
        (Platform.render, status(502), "backend", "0.0.0.0:$PORT"),
        (Platform.render, status(503, "This service has been suspended."), "backend", "suspended"),
        (Platform.hf_spaces, status(503), "backend", "app_port"),
        (Platform.netlify, status(502), "frontend", "upstream returned 502"),
        (Platform.render, status(500), "backend", "raises on startup"),
        (Platform.render, error("timeout"), "backend", "0.0.0.0:$PORT"),
        (Platform.vercel, error("timeout"), "frontend", "hanging"),
        (Platform.render, error("dns", "hostname does not resolve"), "backend", "does not exist"),
        (Platform.vercel, error("blocked", "evil.com is not"), "frontend", "evil.com"),
        (Platform.vercel, error("connection", "refused"), "frontend", "could not connect"),
    ],
)
def test_failures_get_platform_specific_diagnosis(
    platform: Platform, probe: ProbeResult, kind: str, expected: str
) -> None:
    verdict = judge("app", kind, platform, probe)
    assert not verdict.ok
    assert verdict.diagnosis and verdict.diagnosis.startswith(f"app on {platform.value}: ")
    assert expected in verdict.diagnosis


def test_vercel_deployment_not_found_header() -> None:
    # Header names arrive lower-cased with dashes from the probe.
    probe = ProbeResult(
        url=URL, status_code=404, headers={"x-vercel-error": "DEPLOYMENT_NOT_FOUND"}
    )
    assert "no Vercel deployment" in (
        judge("web", "frontend", Platform.vercel, probe).diagnosis or ""
    )


def test_render_no_server_header() -> None:
    probe = ProbeResult(url=URL, status_code=404, headers={"x-render-routing": "no-server"})
    assert "no Render service" in (judge("api", "backend", Platform.render, probe).diagnosis or "")


def test_500_names_the_planned_env_vars() -> None:
    verdict = judge("api", "backend", Platform.render, status(500), ["SECRET_KEY", "DATABASE_URL"])
    assert verdict.diagnosis and "DATABASE_URL, SECRET_KEY" in verdict.diagnosis


@pytest.mark.parametrize(
    "platform, probe, expected",
    [
        (Platform.render, error("timeout"), True),
        (Platform.render, status(503), True),
        (Platform.hf_spaces, status(502), True),
        (Platform.render, status(500), False),
        (Platform.render, error("dns"), False),
        (Platform.vercel, error("timeout"), False),
        (Platform.netlify, status(503), False),
    ],
)
def test_cold_start_only_on_sleepy_platforms(
    platform: Platform, probe: ProbeResult, expected: bool
) -> None:
    assert is_cold_start(platform, probe) is expected
