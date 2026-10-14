"""Dashboard API for apps deployed by the sandbox engine: history, logs, rollback, stop.

Reads come straight from the engine's on-disk store, so they work even when the
engine is disabled (they just return nothing). Rollback and stop need Docker.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from agents.base import LogLevel
from agents.sandbox.docker import SandboxError
from agents.sandbox.engine import DeployError, Engine
from agents.sandbox.router import app_url, router_port
from agents.sandbox.store import AppRecord, Deployment

router = APIRouter(prefix="/api/apps", tags=["apps"])


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return Engine()


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
    apps: list[AppView]


class RollbackRequest(BaseModel):
    deploy_id: str


async def _quiet(message: str, level: LogLevel = LogLevel.info) -> None:
    return None


def _load(engine: Engine, name: str) -> AppRecord:
    try:
        record = engine.store.load(name)
    except ValueError:
        record = None
    if record is None:
        raise HTTPException(status_code=404, detail="App not found")
    return record


@router.get("")
async def list_apps(engine: EngineDep) -> AppsResponse:
    apps = [AppView.from_record(r) for r in engine.store.list()]
    return AppsResponse(router_port=router_port(), apps=apps)


@router.get("/{name}")
async def get_app(name: str, engine: EngineDep) -> AppView:
    return AppView.from_record(_load(engine, name))


@router.get("/{name}/deploys/{deploy_id}/log", response_class=PlainTextResponse)
async def deploy_log(name: str, deploy_id: str, engine: EngineDep) -> str:
    record = _load(engine, name)
    if record.deployment(deploy_id) is None:
        raise HTTPException(status_code=404, detail="Deploy not found")
    path = engine.store.log_path(name, deploy_id)
    return path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""


@router.post("/{name}/rollback")
async def rollback(name: str, body: RollbackRequest, engine: EngineDep) -> AppView:
    _load(engine, name)
    try:
        record = await engine.rollback(name, body.deploy_id, _quiet)
    except DeployError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SandboxError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AppView.from_record(record)


@router.post("/{name}/stop", status_code=204)
async def stop(name: str, engine: EngineDep) -> Response:
    _load(engine, name)
    try:
        await engine.stop(name)
    except SandboxError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(status_code=204)


@router.delete("/{name}", status_code=204)
async def delete(name: str, engine: EngineDep) -> Response:
    _load(engine, name)
    try:
        await engine.stop(name, delete=True)
    except SandboxError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(status_code=204)
