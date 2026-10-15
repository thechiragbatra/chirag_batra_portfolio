"""The probe's URL guard, plus `fetch` against a throwaway local HTTP server.

`fetch` skips the domain check, which is the only way to reach 127.0.0.1 here;
`probe` itself refuses it.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from agents.skills.probe import MAX_BODY_BYTES, _opener, check_url, fetch, probe


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/big":
            self._send(200, b"x" * (MAX_BODY_BYTES * 4))
        elif self.path == "/missing":
            self._send(404, b"nope", {"x-vercel-error": "DEPLOYMENT_NOT_FOUND"})
        elif self.path == "/escape":
            self._send(302, b"", {"Location": "https://169.254.169.254/latest/meta-data"})
        elif self.path == "/host":
            self._send(200, (self.headers.get("Host") or "").encode())
        elif self.path == "/slow":
            threading.Event().wait(1.0)
            self._send(200, b"late")
        else:
            self._send(200, b"<html>ok</html>", {"cf-ray": "abc123"})

    def _send(self, code: int, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.send_response(code)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_: object) -> None:
        pass


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.mark.parametrize(
    "url",
    [
        "https://shop.vercel.app",
        "https://shop.netlify.app/health",
        "https://shop.pages.dev",
        "https://shop-api.onrender.com/",
        "https://acme-shop.hf.space",
    ],
)
def test_check_url_allows_platform_domains(url: str) -> None:
    assert check_url(url) is None


def test_check_url_allows_sandbox_router_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYSMITH_ROUTER_PORT", "8090")
    assert check_url("http://shop.localhost:8090/") is None
    assert check_url("http://shop.localhost:8080/") is not None


@pytest.mark.parametrize(
    "url, reason",
    [
        ("http://shop.vercel.app", "https"),
        ("https://localhost", "not on a free-tier"),
        ("https://127.0.0.1", "not on a free-tier"),
        ("https://169.254.169.254/latest", "not on a free-tier"),
        ("https://vercel.app.evil.com", "not on a free-tier"),
        ("https://evilvercel.app", "not on a free-tier"),
        ("https://user:pw@shop.vercel.app", "credentials"),
        ("postgres://u@ep-x.neon.tech/main", "credentials"),
        ("http://shop.localhost:8000", "https"),
        ("http://a.b.localhost:8080", "https"),
        ("https://shop.localhost:8080", "not on a free-tier"),
    ],
)
def test_check_url_rejects_everything_else(url: str, reason: str) -> None:
    result = check_url(url)
    assert result is not None and reason in result


def test_probe_refuses_blocked_url_without_connecting() -> None:
    result = probe("https://127.0.0.1:1")
    assert result.error == "blocked" and result.status_code is None


def test_fetch_ok_keeps_status_latency_and_selected_headers(server: str) -> None:
    result = fetch(server + "/", timeout=5)
    assert result.status_code == 200 and result.error is None
    assert result.latency_ms is not None and result.latency_ms >= 0
    assert result.headers.get("cf-ray") == "abc123"
    assert "ok" in result.body


def test_fetch_caps_body(server: str) -> None:
    assert len(fetch(server + "/big", timeout=5).body) == MAX_BODY_BYTES


def test_fetch_returns_http_errors_as_results(server: str) -> None:
    result = fetch(server + "/missing", timeout=5)
    assert result.status_code == 404 and result.error is None
    assert result.headers["x-vercel-error"] == "DEPLOYMENT_NOT_FOUND"


def test_fetch_does_not_follow_redirect_off_platform(server: str) -> None:
    result = fetch(server + "/escape", timeout=5, opener=_opener())
    assert result.error is None and result.status_code == 302
    assert result.headers["location"] == "https://169.254.169.254/latest/meta-data"


def test_fetch_times_out(server: str) -> None:
    result = fetch(server + "/slow", timeout=0.2)
    assert result.error == "timeout"


def test_fetch_connection_refused() -> None:
    # Port 1 on loopback is reliably closed.
    result = fetch("http://127.0.0.1:1/", timeout=2)
    assert result.error == "connection"


@pytest.mark.network
@pytest.mark.parametrize(
    "url, header, value",
    [
        (
            "https://deploysmith-no-such-app-7x2q.vercel.app",
            "x-vercel-error",
            "DEPLOYMENT_NOT_FOUND",
        ),
        ("https://deploysmith-no-such-app-7x2q.onrender.com", "x-render-routing", "no-server"),
    ],
)
def test_real_platforms_report_missing_deployments(url: str, header: str, value: str) -> None:
    """The headers diagnose.py relies on, as the platforms actually send them."""
    result = probe(url)
    assert result.status_code == 404 and result.headers.get(header) == value


def test_fetch_connect_to_keeps_the_virtual_host(server: str) -> None:
    result = fetch("http://shop.localhost:8080/host", timeout=5, connect_to=server)
    assert result.status_code == 200 and result.body == "shop.localhost:8080"
