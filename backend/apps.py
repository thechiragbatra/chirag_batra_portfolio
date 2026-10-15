"""Dashboard API for apps deployed by the sandbox engine: history, logs, rollback, stop.

Reads come straight from the engine's on-disk store, so they work even when the
engine is disabled (they just return nothing). Rollback and stop need Docker.
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from agents.base import LogLevel
from agents.sandbox.docker import SandboxError, container_running
from agents.sandbox.engine import DeployError, Engine, default_engine
from agents.sandbox.router import ROUTER_NAME, app_url, router_port
from agents.sandbox.store import AppRecord, CorruptRecord, Deployment

MAX_LOG_RESPONSE_BYTES = 2 * 1024 * 1024

router = APIRouter(prefix="/api/apps", tags=["apps"])


def get_engine() -> Engine:
    """The process-wide engine, shared with the deploy pipeline so per-app locks agree."""
    return default_engine()


EngineDep = Annotated[Engine, Depends(get_engine)]


class AppView(BaseModel):
    name: str
    repo_url: str
    component: str
    framework: str | None
    mode: str
    current: str | None
    url: str | None
    deployments: list[Deployment]

    @classmethod
    def from_record(cls, record: AppRecord) -> AppView:
        newest_first = sorted(record.deployments, key=lambda d: d.id, reverse=True)
        return cls(
            name=record.name,
            repo_url=record.repo_url,
            component=record.component,
            framework=record.framework,
            mode=record.mode,
            current=record.current,
            url=app_url(record.name) if record.current else None,
            deployments=newest_first,
        )


class AppsResponse(BaseModel):
    router_port: int
    engine_enabled: bool
    router_running: bool
    apps: list[AppView]


class RollbackRequest(BaseModel):
    deploy_id: str = Field(pattern=r"^d[0-9]{14}[0-9a-f]{4}$")


def engine_enabled_flag() -> bool:
    return os.getenv("SANDBOX_ENGINE", "").lower() in {"1", "true", "yes"}


async def _quiet(message: str, level: LogLevel = LogLevel.info) -> None:
    return None


def _load(engine: Engine, name: str) -> AppRecord:
    try:
        record = engine.store.load(name)
    except CorruptRecord as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError:
        record = None
    if record is None:
        raise HTTPException(status_code=404, detail="App not found")
    return record


@router.get("")
async def list_apps(engine: EngineDep) -> AppsResponse:
    apps = [AppView.from_record(r) for r in engine.store.list()]
    try:
        router_up = await container_running(ROUTER_NAME)
    except SandboxError:
        router_up = False
    return AppsResponse(
        router_port=router_port(),
        engine_enabled=engine_enabled_flag(),
        router_running=router_up,
        apps=apps,
    )


@router.get("/{name}")
async def get_app(name: str, engine: EngineDep) -> AppView:
    return AppView.from_record(_load(engine, name))


@router.get("/{name}/deploys/{deploy_id}/log", response_class=PlainTextResponse)
async def deploy_log(name: str, deploy_id: str, engine: EngineDep) -> str:
    record = _load(engine, name)
    if record.deployment(deploy_id) is None:
        raise HTTPException(status_code=404, detail="Deploy not found")
    path = engine.store.log_path(name, deploy_id)
    if not path.is_file():
        return ""
    size = path.stat().st_size
    with path.open("rb") as handle:
        if size > MAX_LOG_RESPONSE_BYTES:
            handle.seek(size - MAX_LOG_RESPONSE_BYTES)
        data = handle.read().decode("utf-8", errors="replace")
    if size > MAX_LOG_RESPONSE_BYTES:
        data = f"[showing the last {MAX_LOG_RESPONSE_BYTES // (1024 * 1024)} MB]\n" + data
    return data


@router.post("/{name}/rollback")
async def rollback(name: str, body: RollbackRequest, engine: EngineDep) -> AppView:
    if _load(engine, name).deployment(body.deploy_id) is None:
        raise HTTPException(status_code=404, detail="Deploy not found")
    try:
        record = await engine.rollback(name, body.deploy_id, _quiet)
    except (DeployError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SandboxError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AppView.from_record(record)


@router.post("/{name}/stop", status_code=204)
async def stop(name: str, engine: EngineDep) -> Response:
    _load(engine, name)
    try:
        await engine.stop(name)
    except DeployError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SandboxError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(status_code=204)


@router.delete("/{name}", status_code=204)
async def delete(name: str, engine: EngineDep) -> Response:
    _load(engine, name)
    try:
        await engine.stop(name, delete=True)
    except DeployError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SandboxError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(status_code=204)
