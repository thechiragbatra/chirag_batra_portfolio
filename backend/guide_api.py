"""HTTP API for Smith, the portfolio guide agent (agents/guide/).

    GET  /api/guide        -> {"enabled": bool, "model": str | null}
    POST /api/guide/chat   -> text/event-stream of guide events, one JSON object per event

The model runs on a free tier, so every visitor is rate limited, the whole site has a daily
cap, and repo profiling (a real clone) has its own tighter limit.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from agents.guide.agent import GuideEvent, build_guide, run_guide
from agents.guide.llm import ChatModel, GroqChat, LLMError, guide_enabled
from agents.guide.tools import Toolbox, profile_github_repo

router = APIRouter(prefix="/api/guide")
logger = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 1500
MAX_HISTORY = 16
_CITATION = re.compile(r"\s*\[S\d+\]")


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


class SlidingWindow:
    """At most `limit` events per `window` seconds per key (in memory: one instance)."""

    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window
        self.clock = clock
        self.events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self.clock()
        events = self.events[key]
        while events and now - events[0] >= self.window:
            events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(now)
        return True

    def retry_after(self, key: str) -> int:
        events = self.events.get(key)
        if not events:
            return 0
        return max(1, int(self.window - (self.clock() - events[0])) + 1)


class Limits:
    def __init__(self) -> None:
        self.per_visitor = SlidingWindow(_env_int("GUIDE_RATE_PER_HOUR", 30), 3600)
        self.daily = SlidingWindow(_env_int("GUIDE_DAILY_LIMIT", 500), 86400)
        self.profiles = SlidingWindow(_env_int("GUIDE_PROFILES_PER_HOUR", 5), 3600)
        self.clones = asyncio.Semaphore(2)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    page: str = Field(default="/projects", max_length=100)

    @field_validator("messages")
    @classmethod
    def _ends_with_question(cls, messages: list[ChatMessage]) -> list[ChatMessage]:
        last = messages[-1]
        if last.role != "user":
            raise ValueError("the last message must be from the user")
        if len(last.content) > MAX_MESSAGE_CHARS:
            raise ValueError(f"questions are limited to {MAX_MESSAGE_CHARS} characters")
        return messages


def model_history(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Recent turns for the model. Old citation markers are dropped: their numbering belonged
    to earlier answers and would point at the wrong sources now."""
    recent = messages[-MAX_HISTORY:]
    return [
        {
            "role": m.role,
            "content": _CITATION.sub("", m.content) if m.role == "assistant" else m.content,
        }
        for m in recent
    ]


class GuideService:
    """Holds the compiled graph, the model client and the limits for the app's lifetime."""

    def __init__(
        self,
        model_factory: Callable[[], ChatModel] | None = None,
        toolbox_factory: Callable[[Callable[[str], Awaitable[dict[str, Any]]]], Toolbox]
        | None = None,
        profiler: Callable[[str], Awaitable[dict[str, Any]]] = profile_github_repo,
    ) -> None:
        self.graph = build_guide()
        self.limits = Limits()
        self._model_factory = model_factory or GroqChat
        self._model: ChatModel | None = None
        self._toolbox_factory = toolbox_factory or (lambda p: Toolbox(profiler=p))
        self._profiler = profiler

    def enabled(self) -> bool:
        return self._model is not None or guide_enabled()

    def model(self) -> ChatModel:
        if self._model is None:
            self._model = self._model_factory()
        return self._model

    def limited_profiler(self, visitor: str) -> Callable[[str], Awaitable[dict[str, Any]]]:
        async def profile(url: str) -> dict[str, Any]:
            if not self.limits.profiles.allow(visitor):
                raise RuntimeError("repo profiling limit reached for now; try again later")
            async with self.limits.clones:
                return await self._profiler(url)

        return profile

    def toolbox(self, visitor: str) -> Toolbox:
        return self._toolbox_factory(self.limited_profiler(visitor))


_service: GuideService | None = None


def get_service() -> GuideService:
    global _service
    if _service is None:
        _service = GuideService()
    return _service


def set_service(service: GuideService | None) -> None:
    """Tests swap in a service with a scripted model."""
    global _service
    _service = service


def _sse(event: GuideEvent) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _friendly(exc: LLMError) -> str:
    if exc.status == 429:
        return "Smith is at its free-tier limit right now. Please try again in a minute."
    return "Smith could not reach its language model. Please try again shortly."


@router.get("")
async def guide_status() -> dict[str, Any]:
    service = get_service()
    enabled = service.enabled()
    model = os.getenv("GROQ_MODEL") or "openai/gpt-oss-120b"
    return {"enabled": enabled, "model": model if enabled else None}


@router.post("/chat")
async def guide_chat(body: ChatRequest, request: Request) -> StreamingResponse:
    service = get_service()
    if not service.enabled():
        raise HTTPException(status_code=503, detail="The guide is not configured on this server")
    visitor = request.client.host if request.client else "unknown"
    if not service.limits.per_visitor.allow(visitor):
        wait = service.limits.per_visitor.retry_after(visitor)
        raise HTTPException(
            status_code=429,
            detail=f"You have asked a lot of questions; try again in {max(1, wait // 60)} min",
            headers={"Retry-After": str(wait)},
        )
    if not service.limits.daily.allow("site"):
        raise HTTPException(status_code=429, detail="The guide has reached today's limit")

    model = service.model()
    toolbox = service.toolbox(visitor)
    queue: asyncio.Queue[GuideEvent | None] = asyncio.Queue()

    async def emit(event: GuideEvent) -> None:
        await queue.put(event)

    async def work() -> None:
        try:
            await run_guide(
                service.graph, model_history(body.messages), body.page, model, toolbox, emit
            )
            await queue.put({"type": "done"})
        except LLMError as exc:
            await queue.put({"type": "error", "message": _friendly(exc)})
        except Exception:  # never leak internals to the visitor
            logger.exception("guide run failed")
            await queue.put({"type": "error", "message": "Smith hit an unexpected error."})
        finally:
            await queue.put(None)

    async def stream() -> AsyncIterator[str]:
        task = asyncio.create_task(work())
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if event is None:
                    return
                yield _sse(event)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
