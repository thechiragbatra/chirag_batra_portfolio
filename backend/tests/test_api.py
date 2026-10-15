import json
from collections.abc import AsyncIterator

import httpx
import pytest

from main import app


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-DeploySmith": "1"}
    ) as c:
        yield c


def parse_sse(body: str) -> list[dict]:
    events = []
    for block in body.split("\n\n"):
        data = [line[6:] for line in block.splitlines() if line.startswith("data: ")]
        if data:
            events.append(json.loads("\n".join(data)))
    return events


async def test_rejects_non_github_url(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/deployments", json={"repo_url": "https://gitlab.com/a/b"})
    assert response.status_code == 422


async def test_unknown_deployment_is_404(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/deployments/nope/events")
    assert response.status_code == 404


async def test_create_and_stream_until_done(client: httpx.AsyncClient) -> None:
    created = await client.post(
        "/api/deployments", json={"repo_url": "https://github.com/acme/shop.git"}
    )
    assert created.status_code == 201
    body = created.json()
    assert body["repo_url"] == "https://github.com/acme/shop"

    response = await client.get(f"/api/deployments/{body['id']}/events")
    assert response.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(response.text)

    types = [e["type"] for e in events]
    assert types[-1] == "done"
    assert "log" in types
    done = events[-1]
    assert done["success"] is True
    assert set(done["state"]["agent_status"].values()) == {"done"}

    # Reconnecting with Last-Event-ID replays only what came after it.
    replay = await client.get(
        f"/api/deployments/{body['id']}/events", headers={"Last-Event-ID": str(len(events) - 2)}
    )
    assert [e["type"] for e in parse_sse(replay.text)] == ["done"]


async def test_cors_allows_vite_dev_server(client: httpx.AsyncClient) -> None:
    response = await client.options(
        "/api/deployments",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_writes_without_csrf_header_are_rejected() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as bare:
        response = await bare.post("/api/deployments", json={"repo_url": "https://github.com/a/b"})
        assert response.status_code == 403
        assert (await bare.get("/api/health")).status_code == 200  # reads stay open


async def test_unknown_host_header_is_rejected() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://attacker.example") as c:
        assert (await c.get("/api/health")).status_code == 400
