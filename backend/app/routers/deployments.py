"""Deployment runs: start one, and stream its events over server-sent events.

POST /api/deployments              -> {"id", "repo_url"}
GET  /api/deployments/{id}/events  -> text/event-stream (resumable with Last-Event-ID)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from agents.skills.github_url import normalize_github_url
from app.routers.apps import engine_enabled_flag
from app.services.events import EventAdapter
from app.services.graph import build_graph
from app.services.runs import RunRegistry

router = APIRouter(prefix="/api/deployments")


@lru_cache(maxsize=1)
def registry() -> RunRegistry:
    """Built on first use, after settings are loaded (the agents read them)."""
    return RunRegistry(build_graph())


class CreateDeploymentRequest(BaseModel):
    repo_url: str

    @field_validator("repo_url")
    @classmethod
    def _github_only(cls, value: str) -> str:
        return normalize_github_url(value)


class CreateDeploymentResponse(BaseModel):
    id: str
    repo_url: str


async def start_for_guide(repo_url: str) -> dict[str, str]:
    """The guide's start_deployment tool: the same registry as POST /api/deployments."""
    run = registry().create(repo_url)
    mode = "sandbox engine (real build)" if engine_enabled_flag() else "simulated deploy step"
    return {"id": run.id, "repo": run.repo_url, "mode": mode}


@router.post("", status_code=201)
async def create_deployment(body: CreateDeploymentRequest) -> CreateDeploymentResponse:
    run = registry().create(body.repo_url)
    return CreateDeploymentResponse(id=run.id, repo_url=run.repo_url)


@router.get("/{run_id}/events")
async def deployment_events(
    run_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None),
) -> StreamingResponse:
    run = registry().get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Deployment not found")

    start = int(last_event_id) + 1 if last_event_id and last_event_id.isdigit() else 0

    async def stream() -> AsyncIterator[str]:
        yield "retry: 3000\n\n"
        async for item in run.subscribe(start):
            if await request.is_disconnected():
                return
            if item is None:
                yield ": keep-alive\n\n"
                continue
            index, event = item
            data = EventAdapter.dump_json(event).decode()
            yield f"id: {index}\ndata: {data}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
