"""Apps dashboard API against a temp store; docker calls are stubbed."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from agents.models import Component
from agents.sandbox import engine as engine_mod
from agents.sandbox.engine import Engine
from agents.sandbox.store import AppRecord, Deployment, Store
from app.main import app
from app.routers.apps import get_engine


def deployment(deploy_id: str, status: str = "ready") -> Deployment:
    return Deployment(
        id=deploy_id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        status=status,  # type: ignore[arg-type]
        mode="static",
        component=Component(name="web", kind="frontend", path=".", framework="static"),
    )


OLD, NEW, BAD = "d20260101000000aaaa", "d20260102000000bbbb", "d20260103000000cccc"


@pytest.fixture
def engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Engine:
    store = Store(tmp_path)
    record = AppRecord(
        name="shop",
        repo_url="https://github.com/acme/shop",
        component="web",
        framework="static",
        mode="static",
        current=NEW,
        deployments=[deployment(OLD), deployment(NEW), deployment(BAD, "failed")],
    )
    store.save(record)
    for deploy_id in (OLD, NEW):
        store.deploy_dir("shop", deploy_id).mkdir(parents=True)
    store.log_path("shop", NEW).parent.mkdir(parents=True)
    store.log_path("shop", NEW).write_text("npm ci\nnpm run build\n")

    async def nothing(*_: Any, **__: Any) -> None:
        return None

    monkeypatch.setattr(engine_mod, "reload_router", nothing)
    monkeypatch.setattr(engine_mod.dk, "remove_container", nothing)

    async def no_containers(_: str) -> list[str]:
        return []

    monkeypatch.setattr(engine_mod.dk, "app_containers", no_containers)
    monkeypatch.setattr(engine_mod.dk, "ensure_docker", nothing)

    async def not_running(_: str) -> bool:
        return False

    monkeypatch.setattr("app.routers.apps.container_running", not_running)
    return Engine(store)


@pytest.fixture
async def client(engine: Engine) -> AsyncIterator[httpx.AsyncClient]:
    app.dependency_overrides[get_engine] = lambda: engine
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://test", headers={"X-DeploySmith": "1"}
    ) as c:
        yield c
    app.dependency_overrides.clear()


async def test_list_apps_newest_deploy_first(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/apps")
    assert response.status_code == 200
    body = response.json()
    assert body["router_port"] == 8080
    assert body["engine_enabled"] is False and body["router_running"] is False
    (shop,) = body["apps"]
    assert shop["url"] == "http://shop.localhost:8080" and shop["current"] == NEW
    assert [d["id"] for d in shop["deployments"]] == [BAD, NEW, OLD]
    assert shop["deployments"][1]["component"]["framework"] == "static"


async def test_unknown_and_invalid_names_are_404(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/apps/nope")).status_code == 404
    assert (await client.get("/api/apps/..%2F..%2Fetc")).status_code == 404


async def test_deploy_log(client: httpx.AsyncClient) -> None:
    response = await client.get(f"/api/apps/shop/deploys/{NEW}/log")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "npm ci\nnpm run build\n"
    assert (await client.get(f"/api/apps/shop/deploys/{OLD}/log")).text == ""
    assert (await client.get("/api/apps/shop/deploys/d20990101000000ffff/log")).status_code == 404


async def test_rollback(client: httpx.AsyncClient, engine: Engine) -> None:
    response = await client.post("/api/apps/shop/rollback", json={"deploy_id": OLD})
    assert response.status_code == 200
    assert response.json()["current"] == OLD
    assert engine.store.load("shop").current == OLD  # type: ignore[union-attr]

    failed = await client.post("/api/apps/shop/rollback", json={"deploy_id": BAD})
    assert failed.status_code == 409 and "not a successful deploy" in failed.json()["detail"]


async def test_stop_and_delete(client: httpx.AsyncClient, engine: Engine) -> None:
    assert (await client.post("/api/apps/shop/stop")).status_code == 204
    record = engine.store.load("shop")
    assert record and record.current is None
    assert (await client.get("/api/apps/shop")).json()["url"] is None

    assert (await client.delete("/api/apps/shop")).status_code == 204
    assert engine.store.load("shop") is None
    assert (await client.delete("/api/apps/shop")).status_code == 404


async def test_rollback_to_unknown_or_malformed_deploy(client: httpx.AsyncClient) -> None:
    unknown = await client.post(
        "/api/apps/shop/rollback", json={"deploy_id": "d20990101000000ffff"}
    )
    assert unknown.status_code == 404
    malformed = await client.post("/api/apps/shop/rollback", json={"deploy_id": "../etc"})
    assert malformed.status_code == 422


async def test_log_endpoint_serves_only_the_tail(
    client: httpx.AsyncClient, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("app.routers.apps.MAX_LOG_RESPONSE_BYTES", 10)
    engine.store.log_path("shop", NEW).write_text("0123456789ABCDEFGHIJ")
    text = (await client.get(f"/api/apps/shop/deploys/{NEW}/log")).text
    assert text.endswith("ABCDEFGHIJ") and text.startswith("[showing the last")
