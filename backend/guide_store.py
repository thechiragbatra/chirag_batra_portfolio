"""Smith's memory between requests: run records (traces), feedback and an answer cache.

All in process memory (the site runs as one instance), bounded, and lost on restart. The
only thing written to disk is feedback, appended to a local JSONL file so thumbs-down
answers can become eval cases. Question text never leaves the server: /api/guide/stats
publishes aggregates only.
"""

from __future__ import annotations

import json
import os
import re
import statistics
import time
from collections import Counter, OrderedDict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_RECORDS = 1000
CACHE_TTL_S = 24 * 3600
CACHE_SIZE = 200
# Answers depending on live state (a repo, a deployment, the visitor's screen) are not reused.
UNCACHEABLE_TOOLS = frozenset({"profile_repo", "start_deployment", "describe_view"})

Rating = Literal["up", "down"]


@dataclass
class RunRecord:
    id: str
    started: float
    page: str
    question: str
    answer: str = ""
    tools: list[str] = field(default_factory=list)
    models: list[str] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    steps: list[dict[str, Any]] = field(default_factory=list)
    cached: bool = False
    ok: bool = True
    error: str | None = None
    rating: Rating | None = None


def feedback_path() -> Path:
    return Path(os.getenv("GUIDE_FEEDBACK_FILE") or REPO_ROOT / ".guide" / "feedback.jsonl")


class RunLog:
    def __init__(self, max_records: int = MAX_RECORDS) -> None:
        self.records: OrderedDict[str, RunRecord] = OrderedDict()
        self.max_records = max_records

    def add(self, record: RunRecord) -> None:
        self.records[record.id] = record
        while len(self.records) > self.max_records:
            self.records.popitem(last=False)

    def get(self, run_id: str) -> RunRecord | None:
        return self.records.get(run_id)

    def rate(self, run_id: str, rating: Rating, note: str = "") -> RunRecord | None:
        record = self.records.get(run_id)
        if record is None:
            return None
        record.rating = rating
        path = feedback_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rating": rating,
            "note": note,
            **{
                k: v
                for k, v in asdict(record).items()
                if k in ("id", "page", "question", "answer", "tools", "models")
            },
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return record

    def stats(self, now: float | None = None, window_s: float = 24 * 3600) -> dict[str, Any]:
        """Aggregates for the public dashboard. No question or answer text."""
        now = now or time.time()
        recent = [r for r in self.records.values() if now - r.started <= window_s]
        live = [r for r in recent if not r.cached and r.ok]
        latencies = sorted(r.latency_ms for r in recent if r.ok)
        tools: Counter[str] = Counter(t for r in recent for t in r.tools)
        models: Counter[str] = Counter(m for r in live for m in dict.fromkeys(r.models))
        rated = [r.rating for r in self.records.values() if r.rating]

        def pct(p: float) -> int | None:
            if not latencies:
                return None
            return latencies[min(len(latencies) - 1, int(p * len(latencies)))]

        return {
            "window_hours": round(window_s / 3600),
            "questions": len(recent),
            "answered_from_cache": sum(r.cached for r in recent),
            "errors": sum(not r.ok for r in recent),
            "latency_ms": {"p50": pct(0.5), "p90": pct(0.9)},
            "tokens": {
                "prompt": sum(r.prompt_tokens for r in live),
                "completion": sum(r.completion_tokens for r in live),
            },
            "tokens_per_answer": round(
                statistics.mean(r.prompt_tokens + r.completion_tokens for r in live)
            )
            if live
            else None,
            "models": dict(models.most_common()),
            "tools": dict(tools.most_common()),
            "feedback": {"up": rated.count("up"), "down": rated.count("down")},
        }


def normalize_question(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


@dataclass
class CachedAnswer:
    events: list[dict[str, Any]]
    stored: float


class AnswerCache:
    """Recent single-question answers, replayed for identical questions on the same page."""

    def __init__(self, ttl_s: float = CACHE_TTL_S, size: int = CACHE_SIZE) -> None:
        self.ttl_s = ttl_s
        self.size = size
        self.entries: OrderedDict[tuple[str, str], CachedAnswer] = OrderedDict()

    @staticmethod
    def key(question: str, page: str) -> tuple[str, str]:
        return normalize_question(question), page

    def get(
        self, question: str, page: str, now: float | None = None
    ) -> list[dict[str, Any]] | None:
        key = self.key(question, page)
        entry = self.entries.get(key)
        if entry is None:
            return None
        if (now or time.time()) - entry.stored > self.ttl_s:
            del self.entries[key]
            return None
        self.entries.move_to_end(key)
        return entry.events

    def put(self, question: str, page: str, events: list[dict[str, Any]], tools: list[str]) -> bool:
        if UNCACHEABLE_TOOLS & set(tools):
            return False
        if any(e["type"] == "error" for e in events):
            return False
        self.entries[self.key(question, page)] = CachedAnswer(events, time.time())
        while len(self.entries) > self.size:
            self.entries.popitem(last=False)
        return True
