"""Events streamed to the client over SSE. Mirrors shared/schemas/event.schema.json."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from agents.models import AgentName, AgentStatus, DeploymentState, LogLevel


def _now() -> datetime:
    return datetime.now(UTC)


class _Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(default_factory=_now)


class StatusEvent(_Event):
    type: Literal["status"] = "status"
    agent: AgentName
    status: AgentStatus
    repair_attempts: int


class LogEvent(_Event):
    type: Literal["log"] = "log"
    agent: AgentName | None = None
    level: LogLevel = LogLevel.info
    message: str


class DoneEvent(_Event):
    type: Literal["done"] = "done"
    success: bool
    state: DeploymentState


class ErrorEvent(_Event):
    type: Literal["error"] = "error"
    message: str


Event = Annotated[
    StatusEvent | LogEvent | DoneEvent | ErrorEvent,
    Field(discriminator="type"),
]
EventAdapter: TypeAdapter[Event] = TypeAdapter(Event)
