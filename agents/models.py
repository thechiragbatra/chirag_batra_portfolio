"""Domain models shared by the agents and the backend.

These mirror shared/schemas/state.schema.json, which is the source of truth.
backend/tests/test_schema_sync.py fails if the two drift apart.
"""

from __future__ import annotations

import operator
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

MAX_REPAIR_ATTEMPTS = 3


class AgentName(StrEnum):
    profiler = "profiler"
    strategist = "strategist"
    provisioner = "provisioner"
    healer = "healer"


class AgentStatus(StrEnum):
    idle = "idle"
    running = "running"
    done = "done"
    failed = "failed"


class LogLevel(StrEnum):
    info = "info"
    warn = "warn"
    error = "error"
    success = "success"


class Platform(StrEnum):
    """Free-tier hosting targets only. Paid platforms are deliberately unrepresentable."""

    vercel = "vercel"
    netlify = "netlify"
    cloudflare_pages = "cloudflare_pages"
    render = "render"
    hf_spaces = "hf_spaces"
    neon = "neon"
    supabase = "supabase"
    turso = "turso"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class Component(_Model):
    name: str
    kind: Literal["frontend", "backend", "database"]
    path: str
    framework: str | None = None
    build_command: str | None = None
    start_command: str | None = None
    port: int | None = None


class RepoProfile(_Model):
    name: str
    default_branch: str
    languages: list[str]
    frameworks: list[str]
    components: list[Component]
    env_vars: list[str] = Field(default_factory=list)


class DeploymentTarget(_Model):
    component: str
    platform: Platform
    reason: str
    env_vars: list[str] = Field(default_factory=list)


class DeploymentPlan(_Model):
    targets: list[DeploymentTarget]
    notes: list[str] = Field(default_factory=list)


class DeploymentResult(_Model):
    component: str
    platform: Platform
    status: Literal["live", "failed"]
    url: str | None = None
    attempt: int = Field(ge=0)


class HealthCheck(_Model):
    component: str
    url: str | None = None
    ok: bool
    status_code: int | None = None
    latency_ms: int | None = None
    detail: str


class HealthReport(_Model):
    healthy: bool
    checks: list[HealthCheck]
    diagnosis: str | None = None


def merge_status(
    left: dict[AgentName, AgentStatus], right: dict[AgentName, AgentStatus]
) -> dict[AgentName, AgentStatus]:
    """LangGraph reducer: nodes send only the agents whose status changed."""
    return {**left, **right}


def _all_idle() -> dict[AgentName, AgentStatus]:
    return {name: AgentStatus.idle for name in AgentName}


class DeploymentState(_Model):
    repo_url: str
    repo_profile: RepoProfile | None = None
    deployment_plan: DeploymentPlan | None = None
    deployment_results: list[DeploymentResult] = Field(default_factory=list)
    health_report: HealthReport | None = None
    errors: Annotated[list[str], operator.add] = Field(default_factory=list)
    repair_attempts: int = Field(default=0, ge=0, le=MAX_REPAIR_ATTEMPTS)
    agent_status: Annotated[dict[AgentName, AgentStatus], merge_status] = Field(
        default_factory=_all_idle
    )
