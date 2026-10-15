"""In-memory registry of deployment runs and their event logs.

Each run keeps its full event history, so a client that connects late (or
reconnects with Last-Event-ID) replays everything it missed. Phase 1 has no
database: runs live only as long as the process, capped at MAX_RUNS.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import uuid
from collections import OrderedDict
from collections.abc import AsyncIterator

from langgraph.graph.state import CompiledStateGraph

from agents.models import AgentStatus
from app.services.events import DoneEvent, ErrorEvent, Event
from app.services.graph import run_deployment

logger = logging.getLogger(__name__)

MAX_RUNS = 100


class Run:
    def __init__(self, repo_url: str) -> None:
        self.id = uuid.uuid4().hex
        self.repo_url = repo_url
        self.events: list[Event] = []
        self.finished = False
        self._changed = asyncio.Condition()
        self._task: asyncio.Task[None] | None = None

    async def publish(self, event: Event) -> None:
        async with self._changed:
            self.events.append(event)
            self._changed.notify_all()

    async def _finish(self) -> None:
        async with self._changed:
            self.finished = True
            self._changed.notify_all()

    def _has_news(self, index: int) -> bool:
        return index < len(self.events) or self.finished

    def start(self, graph: CompiledStateGraph) -> None:
        self._task = asyncio.create_task(self._execute(graph), name=f"deployment-{self.id}")

    async def _execute(self, graph: CompiledStateGraph) -> None:
        try:
            state = await run_deployment(graph, self.repo_url, self.publish)
            success = (
                state.health_report is not None
                and state.health_report.healthy
                and AgentStatus.failed not in state.agent_status.values()
            )
            await self.publish(DoneEvent(success=success, state=state))
        except Exception:
            logger.exception("deployment %s crashed", self.id)
            await self.publish(ErrorEvent(message="Internal error while running the deployment"))
        finally:
            await self._finish()

    async def subscribe(
        self, start: int = 0, heartbeat: float = 15.0
    ) -> AsyncIterator[tuple[int, Event] | None]:
        """Yield (index, event) from `start` until the run finishes.

        Yields None every `heartbeat` seconds of silence so the caller can send
        a keep-alive and notice disconnected clients.
        """
        index = start
        while True:
            ready = functools.partial(self._has_news, index)
            async with self._changed:
                try:
                    await asyncio.wait_for(self._changed.wait_for(ready), timeout=heartbeat)
                except TimeoutError:
                    batch, finished = None, False
                else:
                    batch, finished = self.events[index:], self.finished
            if batch is None:
                yield None
                continue
            for event in batch:
                yield index, event
                index += 1
            if finished and index >= len(self.events):
                return


class RunRegistry:
    def __init__(self, graph: CompiledStateGraph, max_runs: int = MAX_RUNS) -> None:
        self._graph = graph
        self._runs: OrderedDict[str, Run] = OrderedDict()
        self._max_runs = max_runs

    def create(self, repo_url: str) -> Run:
        run = Run(repo_url)
        self._runs[run.id] = run
        while len(self._runs) > self._max_runs:
            self._runs.popitem(last=False)
        run.start(self._graph)
        return run

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)
