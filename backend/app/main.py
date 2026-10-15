"""The DeploySmith OS API: middleware, routers and startup.

cd backend
PYTHONPATH=.. uv run uvicorn app.main:app --reload --reload-dir . --reload-dir ../agents
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.trustedhost import TrustedHostMiddleware

from agents.sandbox.engine import default_engine
from app.routers import apps, deployments, guide
from app.settings import CSRF_HEADER, allowed_hosts, cors_origins

logger = logging.getLogger(__name__)

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """With the sandbox engine on, repair state left by a previous run in the background
    (interrupted builds, app containers that are down after a restart)."""
    task = None
    if apps.engine_enabled_flag():

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
    allow_origins=cors_origins(),
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Last-Event-ID", CSRF_HEADER],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts())


@app.middleware("http")
async def require_csrf_header(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    if request.method in _UNSAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        return JSONResponse(status_code=403, content={"detail": f"missing {CSRF_HEADER}: 1 header"})
    return await call_next(request)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(deployments.router)
app.include_router(apps.router)
app.include_router(guide.router)
# Smith can start real runs through the same registry as the Deployer page.
guide.set_deployer(deployments.start_for_guide)
