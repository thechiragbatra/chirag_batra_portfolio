"""Chat model client: Groq's OpenAI-compatible API, streamed.

The guide only depends on the `ChatModel` protocol, so tests run on a scripted fake and
another OpenAI-compatible provider is a base-URL change. The key is read from the
environment (GROQ_API_KEY) and never leaves the server.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_MODEL = "openai/gpt-oss-120b"

Message = dict[str, Any]


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # JSON text, as the model wrote it

    def parsed(self) -> dict[str, Any]:
        """Arguments as a dict; malformed JSON becomes {} and the tool reports what is missing."""
        try:
            value = json.loads(self.arguments or "{}")
        except json.JSONDecodeError:
            return {}
        return value if isinstance(value, dict) else {}


@dataclass
class TextDelta:
    text: str


@dataclass
class Completion:
    """The end of one model turn: its full text and any tool calls it requested."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)


Chunk = TextDelta | Completion


class LLMError(RuntimeError):
    """The model provider failed; `status` is the HTTP status when there was one."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class ChatModel(Protocol):
    def stream(
        self, messages: list[Message], tools: list[dict[str, Any]] | None
    ) -> AsyncIterator[Chunk]: ...


def guide_enabled() -> bool:
    return bool(os.getenv("GROQ_API_KEY"))


def accumulate_tool_calls(calls: dict[int, dict[str, str]], deltas: list[dict[str, Any]]) -> None:
    """Merge streamed tool-call fragments (keyed by index) into whole calls."""
    for delta in deltas:
        slot = calls.setdefault(int(delta.get("index", 0)), {"id": "", "name": "", "arguments": ""})
        if delta.get("id"):
            slot["id"] = delta["id"]
        function = delta.get("function") or {}
        if function.get("name"):
            slot["name"] = function["name"]
        slot["arguments"] += function.get("arguments") or ""


# Groq's free tier gives each model its own quota (about 8K tokens/minute, 200K/day), so
# when one is exhausted the next carries on. Override with GROQ_FALLBACK_MODELS ("" = none).
FALLBACK_MODELS = ("openai/gpt-oss-20b", "qwen/qwen3.8-27b")
MAX_RETRY_WAIT_S = 12.0
_RETRY_IN = re.compile(r"try again in (?:(\d+)m)?([\d.]+)(ms|s)")


class _Unavailable(Exception):
    """This model cannot serve the request right now (raised before anything streams)."""

    def __init__(self, error: LLMError, wait: float | None) -> None:
        self.error = error
        self.wait = wait


def retry_after(detail: str) -> float | None:
    """Seconds from Groq's "Please try again in 1m2.5s" hint, if present."""
    match = _RETRY_IN.search(detail)
    if not match:
        return None
    minutes, value, unit = match.groups()
    seconds = float(value) / (1000 if unit == "ms" else 1)
    return seconds + 60 * int(minutes or 0)


def configured_models() -> list[str]:
    primary = os.getenv("GROQ_MODEL") or DEFAULT_MODEL
    raw = os.getenv("GROQ_FALLBACK_MODELS")
    fallbacks = FALLBACK_MODELS if raw is None else [m.strip() for m in raw.split(",") if m.strip()]
    return [primary, *[m for m in fallbacks if m != primary]]


class GroqChat:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 60.0,
        max_tokens: int = 512,
        transport: httpx.AsyncBaseTransport | None = None,
        fallbacks: list[str] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise LLMError("GROQ_API_KEY is not set")
        models = configured_models()
        if model:
            models = [model, *(fallbacks if fallbacks is not None else models[1:])]
        elif fallbacks is not None:
            models = [models[0], *fallbacks]
        self.models = list(dict.fromkeys(models))
        self.model = self.models[0]
        # Groq counts the reserved completion length against the per-minute quota, so
        # keep it to what a few-sentence answer (plus brief reasoning) needs.
        self.max_tokens = max_tokens
        self._sleep = sleep
        self._client = httpx.AsyncClient(
            base_url=base_url or os.getenv("GROQ_BASE_URL") or GROQ_BASE_URL,
            timeout=timeout,
            headers={"Authorization": f"Bearer {key}"},
            transport=transport,
        )

    def _body(
        self, model: str, messages: list[Message], tools: list[dict[str, Any]] | None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "temperature": 0.2,
            "max_completion_tokens": self.max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"  # fast answers; the tools do the heavy lifting
        return body

    async def stream(
        self, messages: list[Message], tools: list[dict[str, Any]] | None
    ) -> AsyncIterator[Chunk]:
        """Stream from the first model that can serve the request. Rate limits with a short
        wait are retried once; longer waits and unknown models move on to the next model.
        Retries only happen before anything has been streamed, so text is never repeated."""
        last: LLMError | None = None
        for model in self.models:
            for attempt in range(2):
                try:
                    async for chunk in self._stream_once(model, messages, tools):
                        yield chunk
                    self.model = model
                    return
                except _Unavailable as exc:
                    last = exc.error
                    if attempt == 0 and exc.wait is not None and exc.wait <= MAX_RETRY_WAIT_S:
                        await self._sleep(exc.wait + 0.25)
                        continue
                    break
        assert last is not None
        raise last

    async def _stream_once(
        self, model: str, messages: list[Message], tools: list[dict[str, Any]] | None
    ) -> AsyncIterator[Chunk]:
        text: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        try:
            async with self._client.stream(
                "POST", "/chat/completions", json=self._body(model, messages, tools)
            ) as response:
                if response.status_code != 200:
                    detail = (await response.aread()).decode(errors="replace")[:400]
                    error = LLMError(
                        f"model API returned {response.status_code}: {detail}", response.status_code
                    )
                    if response.status_code == 429:
                        raise _Unavailable(error, retry_after(detail))
                    if response.status_code in (400, 404) and "model" in detail.lower():
                        raise _Unavailable(error, None)  # unknown or retired model
                    if response.status_code >= 500:
                        raise _Unavailable(error, 1.0)
                    raise error
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    event = json.loads(data)
                    if event.get("error"):
                        raise LLMError(str(event["error"]))
                    for choice in event.get("choices", []):
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            text.append(delta["content"])
                            yield TextDelta(delta["content"])
                        if delta.get("tool_calls"):
                            accumulate_tool_calls(calls, delta["tool_calls"])
        except httpx.HTTPError as exc:
            if not text:
                raise _Unavailable(LLMError(f"model API unreachable: {exc}"), 1.0) from exc
            raise LLMError(f"model API unreachable: {exc}") from exc
        tool_calls = [
            ToolCall(id=c["id"] or f"call_{i}", name=c["name"], arguments=c["arguments"])
            for i, c in sorted(calls.items())
            if c["name"]
        ]
        yield Completion(text="".join(text), tool_calls=tool_calls)

    async def aclose(self) -> None:
        await self._client.aclose()
