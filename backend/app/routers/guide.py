"""HTTP API for Smith, the portfolio guide agent (agents/guide/).

    GET  /api/guide           -> {"enabled": bool, "model": str | null, "starters": {...}}
    POST /api/guide/chat      -> text/event-stream of guide events, one JSON object per event
    POST /api/guide/feedback  -> rate an answer (thumbs up or down)
    GET  /api/guide/stats     -> aggregate usage for the "How Smith works" page (no text)

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
import uuid
from collections import defaultdict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from agents.guide.agent import GuideEvent, Outcome, build_guide, run_guide
from agents.guide.followups import PAGE_STARTERS
from agents.guide.llm import ChatModel, GroqChat, LLMError, configured_models, guide_enabled
from agents.guide.tools import Toolbox, profile_github_repo
from app.services.guide_store import AnswerCache, RunLog, RunRecord

router = APIRouter(prefix="/api/guide")
logger = logging.getLogger(__name__)

MAX_MESSAGE_CHARS = 1500
MAX_HISTORY = 16
_CITATION = re.compile(r"\s*[\[【]\s*(?:\*\*)?\s*S\d+[^\]】]*[\]】]")


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
        self.daily = SlidingWindow(_env_int("GUIDE_DAILY_LIMIT", 150), 86400)
        self.profiles = SlidingWindow(_env_int("GUIDE_PROFILES_PER_HOUR", 5), 3600)
        self.clones = asyncio.Semaphore(2)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    page: str = Field(default="/projects", max_length=100)
    # What the visitor's screen shows (e.g. the Lab's customer), for describe_view.
    view: dict[str, Any] | None = None

    @field_validator("view")
    @classmethod
    def _small_view(cls, view: dict[str, Any] | None) -> dict[str, Any] | None:
        if view is not None and len(json.dumps(view)) > 4000:
            raise ValueError("view is too large")
        return view

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


Deployer = Callable[[str], Awaitable[dict[str, Any]]]


class GuideService:
    """Holds the compiled graph, the model client, limits, run log and cache."""

    def __init__(
        self,
        model_factory: Callable[[], ChatModel] | None = None,
        profiler: Callable[[str], Awaitable[dict[str, Any]]] = profile_github_repo,
        deployer: Deployer | None = None,
    ) -> None:
        self.graph = build_guide()
        self.limits = Limits()
        self.runs = RunLog()
        self.cache = AnswerCache()
        self._model_factory = model_factory or GroqChat
        self._model: ChatModel | None = None
        self._profiler = profiler
        self.deployer = deployer

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

    def limited_deployer(self, visitor: str) -> Deployer | None:
        deployer = self.deployer
        if deployer is None:
            return None

        async def deploy(url: str) -> dict[str, Any]:
            # Each deployment clones the repo too, so it shares the profiling limit.
            if not self.limits.profiles.allow(visitor):
                raise RuntimeError("deployment limit reached for now; try again later")
            return await deployer(url)

        return deploy

    def toolbox(
        self, visitor: str, page: str, view: dict[str, Any] | None, question: str = ""
    ) -> Toolbox:
        return Toolbox(
            question=question,
            profiler=self.limited_profiler(visitor),
            deployer=self.limited_deployer(visitor),
            page=page,
            view=view,
        )


_service: GuideService | None = None
_deployer: Deployer | None = None


def get_service() -> GuideService:
    global _service
    if _service is None:
        _service = GuideService(deployer=_deployer)
    return _service


def set_service(service: GuideService | None) -> None:
    """Tests swap in a service with a scripted model."""
    global _service
    _service = service


def set_deployer(deployer: Deployer) -> None:
    """main.py hands over the deployment registry, so Smith can start real runs."""
    global _deployer
    _deployer = deployer
    if _service is not None:
        _service.deployer = deployer


def _sse(event: GuideEvent) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _friendly(exc: LLMError) -> str:
    if exc.status == 429:
        return "Smith is at its free-tier limit right now. Please try again in a minute."
    return "Smith could not reach its language model. Please try again shortly."


def _record(record: RunRecord, outcome: Outcome) -> None:
    trace = outcome.trace
    record.answer = outcome.answer
    record.tools = outcome.tools
    record.models = trace.models
    record.prompt_tokens = trace.prompt_tokens
    record.completion_tokens = trace.completion_tokens
    record.steps = trace.steps


async def replay(events: list[GuideEvent]) -> AsyncIterator[GuideEvent]:
    """A cached answer, streamed back a few words at a time so it still reads as typing."""
    words: list[str] = []
    for event in events:
        if event["type"] == "token":
            words.append(event["text"])
            if len(words) < 6:
                continue
            yield {"type": "token", "text": "".join(words)}
            words = []
            await asyncio.sleep(0.012)
            continue
        if words:
            yield {"type": "token", "text": "".join(words)}
            words = []
        yield event
    if words:
        yield {"type": "token", "text": "".join(words)}


@router.get("")
async def guide_status() -> dict[str, Any]:
    service = get_service()
    enabled = service.enabled()
    return {
        "enabled": enabled,
        "model": configured_models()[0] if enabled else None,
        "starters": {page: list(items) for page, items in PAGE_STARTERS.items()},
    }


class FeedbackRequest(BaseModel):
    run: str = Field(pattern=r"^[0-9a-f]{32}$")
    rating: Literal["up", "down"]
    note: str = Field(default="", max_length=500)


@router.post("/feedback", status_code=204)
async def guide_feedback(body: FeedbackRequest) -> None:
    if get_service().runs.rate(body.run, body.rating, body.note) is None:
        raise HTTPException(status_code=404, detail="That answer is no longer on record")


@router.get("/stats")
async def guide_stats() -> dict[str, Any]:
    service = get_service()
    return {"enabled": service.enabled(), **service.runs.stats()}


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

    question = body.messages[-1].content
    record = RunRecord(id=uuid.uuid4().hex, started=time.time(), page=body.page, question=question)
    # Only a conversation's first question is reusable: later ones depend on what came before.
    cacheable = len(body.messages) == 1 and not body.view
    cached = service.cache.get(question, body.page) if cacheable else None
    if cached is None and not service.limits.daily.allow("site"):
        raise HTTPException(status_code=429, detail="The guide has reached today's limit")

    queue: asyncio.Queue[GuideEvent | None] = asyncio.Queue()
    recorded: list[GuideEvent] = []

    async def emit(event: GuideEvent) -> None:
        recorded.append(event)
        await queue.put(event)

    async def work() -> None:
        started = time.perf_counter()
        await queue.put({"type": "meta", "run": record.id, "cached": cached is not None})
        try:
            if cached is not None:
                record.cached = True
                async for event in replay(cached):
                    await queue.put(event)
                record.answer = "".join(e["text"] for e in cached if e["type"] == "token")
            else:
                toolbox = service.toolbox(visitor, body.page, body.view, question)
                outcome = await run_guide(
                    service.graph,
                    model_history(body.messages),
                    body.page,
                    service.model(),
                    toolbox,
                    emit,
                )
                _record(record, outcome)
                if cacheable:
                    service.cache.put(question, body.page, recorded, outcome.tools)
            await queue.put({"type": "done"})
        except LLMError as exc:
            record.ok, record.error = False, f"model: {exc.status}"
            await queue.put({"type": "error", "message": _friendly(exc)})
        except Exception:  # never leak internals to the visitor
            logger.exception("guide run failed")
            record.ok, record.error = False, "internal"
            await queue.put({"type": "error", "message": "Smith hit an unexpected error."})
        finally:
            record.latency_ms = round((time.perf_counter() - started) * 1000)
            service.runs.add(record)
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
