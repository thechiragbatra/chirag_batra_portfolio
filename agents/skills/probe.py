"""Hardened HTTP health probe for deployed components.

The healer only ever probes URLs the provisioner produced, but the probe does not
trust them either:
- https only, and the host must sit on a free-tier platform domain (no localhost,
  private IPs or arbitrary sites, so a bad URL cannot turn the healer into an SSRF proxy),
- redirects are followed only while they stay on those domains; a redirect elsewhere
  (e.g. to a custom domain) is returned as the 3xx response itself, not followed,
- at most MAX_BODY_BYTES of the body are read, and every request has a timeout.
Standard library only (urllib), run in a worker thread by the caller.
"""

from __future__ import annotations

import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from email.message import Message
from typing import Literal
from urllib.parse import urlsplit

MAX_BODY_BYTES = 2048
USER_AGENT = "DeploySmith-Healer/0.1 (+health check)"

# Hosting domains a deployed component may live on. Databases are never probed over HTTP.
ALLOWED_HOST_SUFFIXES: tuple[str, ...] = (
    ".vercel.app",
    ".netlify.app",
    ".pages.dev",
    ".onrender.com",
    ".hf.space",
)

# Response headers worth keeping for diagnosis (lower-cased).
_KEPT_HEADERS = ("server", "location", "x-vercel-error", "x-render-routing", "cf-ray")

ProbeError = Literal["blocked", "dns", "timeout", "connection", "tls"]


@dataclass(frozen=True)
class ProbeResult:
    url: str
    status_code: int | None = None
    latency_ms: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    body: str = ""
    error: ProbeError | None = None
    error_detail: str = ""


def check_url(url: str) -> str | None:
    """Why `url` may not be probed, or None if it is allowed."""
    parts = urlsplit(url)
    if parts.scheme != "https":
        return "only https URLs are probed"
    host = (parts.hostname or "").lower()
    if not host.endswith(ALLOWED_HOST_SUFFIXES):
        return f"{host or 'empty host'} is not on a free-tier platform domain"
    if parts.username or parts.password:
        return "URLs with credentials are not probed"
    return None


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only if its target passes `check_url`.

    Returning None makes urllib surface the 3xx as an HTTPError, which `fetch`
    reports as the response, so the platform answering with a redirect still counts.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        if check_url(newurl) is not None:
            return None
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener() -> urllib.request.OpenerDirector:
    # No ProxyHandler: the host's proxy env vars must not reroute probes.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}), _SafeRedirects())


def _kept_headers(headers: Message) -> dict[str, str]:
    return {name: headers[name] for name in _KEPT_HEADERS if headers.get(name) is not None}


def _read_body(response) -> str:  # type: ignore[no-untyped-def]
    return response.read(MAX_BODY_BYTES).decode("utf-8", errors="replace")


def _classify(exc: BaseException) -> tuple[ProbeError, str]:
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, socket.gaierror):
        return "dns", "hostname does not resolve"
    if isinstance(reason, TimeoutError | socket.timeout):
        return "timeout", "no response before the timeout"
    if isinstance(reason, ssl.SSLError):
        return "tls", f"TLS error: {reason}"
    return "connection", str(reason)


def fetch(
    url: str, timeout: float, opener: urllib.request.OpenerDirector | None = None
) -> ProbeResult:
    """GET `url` without the domain check. Use `probe` unless you are a test."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT}, method="GET")
    started = time.monotonic()

    def elapsed() -> int:
        return round((time.monotonic() - started) * 1000)

    try:
        with (opener or _opener()).open(request, timeout=timeout) as response:
            return ProbeResult(
                url=url,
                status_code=response.status,
                latency_ms=elapsed(),
                headers=_kept_headers(response.headers),
                body=_read_body(response),
            )
    except urllib.error.HTTPError as exc:
        with exc:
            return ProbeResult(
                url=url,
                status_code=exc.code,
                latency_ms=elapsed(),
                headers=_kept_headers(exc.headers),
                body=_read_body(exc),
            )
    except (urllib.error.URLError, OSError) as exc:
        kind, detail = _classify(exc)
        return ProbeResult(url=url, latency_ms=elapsed(), error=kind, error_detail=detail)


def probe(url: str, timeout: float = 15.0) -> ProbeResult:
    """Health-check a deployed URL. Blocking; call it via asyncio.to_thread."""
    reason = check_url(url)
    if reason is not None:
        return ProbeResult(url=url, error="blocked", error_detail=reason)
    return fetch(url, timeout)
