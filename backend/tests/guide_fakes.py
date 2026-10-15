"""A scripted ChatModel for guide tests: each turn is text and/or tool calls."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from agents.guide.llm import Chunk, Completion, Message, TextDelta, ToolCall


@dataclass
class Turn:
    text: str = ""
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)


class ScriptedModel:
    def __init__(self, *turns: Turn) -> None:
        self.turns = list(turns)
        self.seen: list[tuple[list[Message], list[dict[str, Any]] | None]] = []

    async def stream(
        self, messages: list[Message], tools: list[dict[str, Any]] | None
    ) -> AsyncIterator[Chunk]:
        self.seen.append(([dict(m) for m in messages], tools))
        turn = self.turns.pop(0) if self.turns else Turn(text="(no more turns)")
        for word in turn.text.split(" ") if turn.text else []:
            yield TextDelta(word + " ")
        calls = [
            ToolCall(id=f"call_{len(self.seen)}_{i}", name=name, arguments=json.dumps(args))
            for i, (name, args) in enumerate(turn.calls)
        ]
        yield Completion(text=turn.text, tool_calls=calls)
