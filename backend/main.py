"""DeploySmith OS API.

Run from backend/:  PYTHONPATH=.. uv run uvicorn main:app --reload
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from events import EventAdapter
from graph import build_graph
from runs import RunRegistry
from validation import normalize_github_url


def _cors_origins() -> list[str]:
    raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


class CreateDeploymentRequest(BaseModel):
    repo_url: str

    @field_validator("repo_url")
    @classmethod
    def _github_only(cls, value: str) -> str:
        return normalize_github_url(value)


class CreateDeploymentResponse(BaseModel):
    id: str
    repo_url: str


app = FastAPI(title="DeploySmith OS", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Last-Event-ID"],
)
registry = RunRegistry(build_graph())


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/deployments", status_code=201)
async def create_deployment(body: CreateDeploymentRequest) -> CreateDeploymentResponse:
    run = registry.create(body.repo_url)
    return CreateDeploymentResponse(id=run.id, repo_url=run.repo_url)


@app.get("/api/deployments/{run_id}/events")
async def deployment_events(
    run_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None),
) -> StreamingResponse:
    run = registry.get(run_id)
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
