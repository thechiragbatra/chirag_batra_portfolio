"""Chat model client: Groq's OpenAI-compatible API, streamed.

The guide only depends on the `ChatModel` protocol, so tests run on a scripted fake and
another OpenAI-compatible provider is a base-URL change. The key is read from the
environment (GROQ_API_KEY) and never leaves the server.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
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


class GroqChat:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str = GROQ_BASE_URL,
        timeout: float = 60.0,
        max_tokens: int = 700,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        key = api_key or os.getenv("GROQ_API_KEY")
        if not key:
            raise LLMError("GROQ_API_KEY is not set")
        self.model = model or os.getenv("GROQ_MODEL") or DEFAULT_MODEL
        self.max_tokens = max_tokens
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {key}"},
            transport=transport,
        )

    def _body(self, messages: list[Message], tools: list[dict[str, Any]] | None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.2,
            "max_completion_tokens": self.max_tokens,
        }
        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        if self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = "low"  # fast answers; the tools do the heavy lifting
        return body

    async def stream(
        self, messages: list[Message], tools: list[dict[str, Any]] | None
    ) -> AsyncIterator[Chunk]:
        text: list[str] = []
        calls: dict[int, dict[str, str]] = {}
        try:
            async with self._client.stream(
                "POST", "/chat/completions", json=self._body(messages, tools)
            ) as response:
                if response.status_code != 200:
                    detail = (await response.aread()).decode(errors="replace")[:300]
                    raise LLMError(
                        f"model API returned {response.status_code}: {detail}", response.status_code
                    )
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
            raise LLMError(f"model API unreachable: {exc}") from exc
        tool_calls = [
            ToolCall(id=c["id"] or f"call_{i}", name=c["name"], arguments=c["arguments"])
            for i, c in sorted(calls.items())
            if c["name"]
        ]
        yield Completion(text="".join(text), tool_calls=tool_calls)

    async def aclose(self) -> None:
        await self._client.aclose()
