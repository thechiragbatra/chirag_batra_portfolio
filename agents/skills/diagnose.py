"""Turn a health probe into a verdict and, when it failed, an actionable diagnosis.

Pure rules over the status code, a few platform headers and the start of the body.
Each rule names the platform-specific fix the provisioner should apply on the
next repair attempt.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from agents.models import Platform
from agents.skills.probe import ProbeResult

_VERCEL_PROTECTION = "Vercel Deployment Protection is on; disable it for production or add a bypass"

# Platforms whose free tier sleeps when idle, so the first request may be slow or 503.
SLEEPY_PLATFORMS = frozenset({Platform.render, Platform.hf_spaces})


@dataclass(frozen=True)
class Verdict:
    ok: bool
    detail: str
    diagnosis: str | None = None


def is_cold_start(platform: Platform, probe: ProbeResult) -> bool:
    """Worth one retry: a sleeping free-tier service often times out or 502/503s while waking."""
    if platform not in SLEEPY_PLATFORMS:
        return False
    return probe.error == "timeout" or probe.status_code in {502, 503}


def _missing_env_hint(env_vars: list[str]) -> str:
    if not env_vars:
        return ""
    return f"; confirm these env vars are set: {', '.join(sorted(env_vars))}"


def _error_verdict(component: str, platform: Platform, probe: ProbeResult) -> Verdict:
    where = f"{component} on {platform.value}"
    match probe.error:
        case "blocked":
            return Verdict(
                False,
                f"Not probed: {probe.error_detail}",
                f"{where}: deployment URL is not on the platform's domain ({probe.error_detail})",
            )
        case "dns":
            return Verdict(
                False,
                "Hostname does not resolve",
                f"{where}: the project does not exist under this name; recreate it",
            )
        case "timeout":
            fix = (
                "the service is crashing on boot or not listening on 0.0.0.0:$PORT"
                if platform in SLEEPY_PLATFORMS
                else "the deployment is hanging; redeploy and check the build logs"
            )
            return Verdict(False, "Timed out waiting for a response", f"{where}: {fix}")
        case _:
            fix = (
                "the sandbox router is not running; redeploy to start it"
                if platform is Platform.sandbox
                else f"could not connect ({probe.error_detail or probe.error})"
            )
            return Verdict(False, probe.error_detail or "Connection failed", f"{where}: {fix}")


def _status_diagnosis(
    platform: Platform, probe: ProbeResult, kind: str, env_vars: list[str]
) -> str:
    code = probe.status_code
    body = probe.body.lower()
    vercel_error = probe.headers.get("x-vercel-error", "")

    if code in {401, 403}:
        if platform is Platform.vercel:
            return _VERCEL_PROTECTION
        if platform is Platform.hf_spaces:
            return "the Space is private; make it public"
        return f"the platform returned {code}; the deployment is not publicly reachable"

    if code == 404 and platform is Platform.sandbox and "no app is deployed" in body:
        return "no live deploy for this app in the sandbox; redeploy"
    if code == 404:
        if vercel_error == "DEPLOYMENT_NOT_FOUND" or "deployment could not be found" in body:
            return "no Vercel deployment at this URL; redeploy and alias it to production"
        if platform is Platform.netlify and "not found" in body and "site" in body:
            return "Netlify site not found; recreate the site"
        if platform is Platform.render and probe.headers.get("x-render-routing") == "no-server":
            return "no Render service at this URL; recreate the web service"
        if kind == "frontend":
            return (
                "the root path 404s: set the build output directory "
                "(dist/ for Vite, build/ for CRA, out/ for a Next.js export)"
            )
        return "the root path 404s: serve a health route at / or point the check at one"

    if code in {502, 503, 504}:
        if platform is Platform.sandbox:
            return (
                "the app container is not answering on 0.0.0.0:$PORT; "
                "check its logs on the Apps page"
            )
        if platform is Platform.render and "suspended" in body:
            return "the Render service is suspended; resume it in the dashboard"
        if platform is Platform.render:
            return "start command must bind the server to 0.0.0.0:$PORT"
        if platform is Platform.hf_spaces:
            return "the Space is not serving; set app_port in README.md to the port the app binds"
        return f"upstream returned {code}; redeploy and check the build logs"

    if code is not None and code >= 500:
        return f"the app raises on startup or on GET /{_missing_env_hint(env_vars)}"

    return f"unexpected status {code}"


def _is_vercel_login(platform: Platform, location: str | None) -> bool:
    """Protected Vercel deployments redirect visitors to vercel.com/sso-api to sign in."""
    if platform is not Platform.vercel or not location:
        return False
    parts = urlsplit(location)
    return parts.hostname == "vercel.com" and parts.path.startswith("/sso-api")


def judge(
    component: str,
    kind: str,
    platform: Platform,
    probe: ProbeResult,
    env_vars: list[str] | None = None,
) -> Verdict:
    """Healthy means a 2xx or 3xx response (except a redirect to a login wall).

    Anything else comes with a diagnosis.
    """
    if probe.error is not None:
        return _error_verdict(component, platform, probe)

    code = probe.status_code
    location = probe.headers.get("location")
    if _is_vercel_login(platform, location):
        detail = f"HTTP {code} -> Vercel login"
        return Verdict(False, detail, f"{component} on {platform.value}: {_VERCEL_PROTECTION}")
    if code is not None and 200 <= code < 400:
        return Verdict(True, f"HTTP {code} -> {location}" if location else f"HTTP {code}")

    diagnosis = _status_diagnosis(platform, probe, kind, env_vars or [])
    return Verdict(False, f"HTTP {code}", f"{component} on {platform.value}: {diagnosis}")
