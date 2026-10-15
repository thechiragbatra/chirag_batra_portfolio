"""DeploySmith OS API.

Run from backend/:  PYTHONPATH=.. uv run uvicorn main:app --reload
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel, field_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agents.sandbox.engine import default_engine
from apps import engine_enabled_flag
from apps import router as apps_router
from events import EventAdapter
from graph import build_graph
from guide_api import router as guide_router
from runs import RunRegistry
from validation import normalize_github_url

logger = logging.getLogger(__name__)

# Every state-changing request must carry this header. Browsers cannot attach a custom
# header cross-origin without a CORS preflight, which the allowlist below rejects, so a
# random web page can no longer stop, delete or start deployments on this machine.
CSRF_HEADER = "X-DeploySmith"
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _allowed_hosts() -> list[str]:
    """Host header allowlist (blocks DNS rebinding). Set ALLOWED_HOSTS when hosting."""
    raw = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
    return [host.strip() for host in raw.split(",") if host.strip()]


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


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """With the sandbox engine on, repair state left by a previous run in the background
    (interrupted builds, app containers that are down after a restart)."""
    task = None
    if engine_enabled_flag():

        async def reconcile() -> None:
            try:
                for action in await default_engine().reconcile():
                    logger.warning("sandbox reconcile: %s", action)
            except Exception:
                logger.exception("sandbox reconcile failed")

        task = asyncio.create_task(reconcile())
    yield
    if task is not None and not task.done():
        task.cancel()


app = FastAPI(title="DeploySmith OS", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Last-Event-ID", CSRF_HEADER],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_allowed_hosts())


@app.middleware("http")
async def require_csrf_header(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.method in _UNSAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        return JSONResponse(status_code=403, content={"detail": f"missing {CSRF_HEADER}: 1 header"})
    return await call_next(request)


registry = RunRegistry(build_graph())
app.include_router(apps_router)
app.include_router(guide_router)


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
