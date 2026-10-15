"""LangGraph pipeline: profiler -> strategist -> provisioner -> healer.

The healer can send the run back to the provisioner, at most
MAX_REPAIR_ATTEMPTS times. Each node wraps an `Agent`: the wrapper emits status
events, binds a logger, and turns exceptions into a `failed` status, which
ends the run.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents import Agent, default_agents
from agents.models import MAX_REPAIR_ATTEMPTS, AgentName, AgentStatus, DeploymentState, LogLevel
from app.services.events import Event, LogEvent, StatusEvent

EmitFn = Callable[[Event], Awaitable[None]]
NodeFn = Callable[[DeploymentState, RunnableConfig], Awaitable[dict[str, Any]]]

PIPELINE: tuple[AgentName, ...] = (
    AgentName.profiler,
    AgentName.strategist,
    AgentName.provisioner,
    AgentName.healer,
)


async def _discard(_: Event) -> None:
    return None


def _emitter(config: RunnableConfig) -> EmitFn:
    return config.get("configurable", {}).get("emit", _discard)


def _make_node(agent: Agent) -> NodeFn:
    name = agent.name

    async def node(state: DeploymentState, config: RunnableConfig) -> dict[str, Any]:
        emit = _emitter(config)
        repairs = state.repair_attempts

        async def set_status(status: AgentStatus) -> None:
            await emit(StatusEvent(agent=name, status=status, repair_attempts=repairs))

        async def log(message: str, level: LogLevel = LogLevel.info) -> None:
            await emit(LogEvent(agent=name, level=level, message=message))

        await set_status(AgentStatus.running)
        try:
            update: dict[str, Any] = dict(await agent.run(state, log))
        except Exception as exc:  # an agent crash fails the run, never the server
            await log(f"{type(exc).__name__}: {exc}", LogLevel.error)
            await set_status(AgentStatus.failed)
            return {"agent_status": {name: AgentStatus.failed}, "errors": [f"{name}: {exc}"]}

        status = AgentStatus.done
        report = update.get("health_report")
        if name is AgentName.healer and report is not None and not report.healthy:
            if repairs < MAX_REPAIR_ATTEMPTS:
                repairs += 1
                update["repair_attempts"] = repairs
                await log(f"Requesting repair {repairs}/{MAX_REPAIR_ATTEMPTS}", LogLevel.warn)
            else:
                status = AgentStatus.failed
                message = f"Deployment still unhealthy after {MAX_REPAIR_ATTEMPTS} repair attempts"
                await log(message, LogLevel.error)
                update["errors"] = [*update.get("errors", []), message]

        await set_status(status)
        update["agent_status"] = {name: status}
        return update

    node.__name__ = f"{name}_node"
    return node


def _continue_unless_failed(name: AgentName, next_node: str) -> Callable[[DeploymentState], str]:
    def route(state: DeploymentState) -> str:
        return END if state.agent_status[name] == AgentStatus.failed else next_node

    return route


def route_after_healer(state: DeploymentState) -> str:
    """Loop back to the provisioner while unhealthy; the healer node enforces the cap."""
    if state.agent_status[AgentName.healer] == AgentStatus.failed:
        return END
    report = state.health_report
    if report is not None and not report.healthy:
        return AgentName.provisioner.value
    return END


def build_graph(agents: Sequence[Agent] | None = None) -> CompiledStateGraph:
    """Compile the pipeline. Pass `agents` to swap implementations (e.g. in tests)."""
    by_name = {agent.name: agent for agent in (agents if agents is not None else default_agents())}
    missing = set(PIPELINE) - set(by_name)
    if missing:
        raise ValueError(f"missing agents: {sorted(missing)}")

    graph = StateGraph(DeploymentState)
    for name in PIPELINE:
        graph.add_node(name.value, _make_node(by_name[name]))

    graph.add_edge(START, PIPELINE[0].value)
    for current, nxt in zip(PIPELINE, PIPELINE[1:], strict=False):
        graph.add_conditional_edges(
            current.value, _continue_unless_failed(current, nxt.value), [nxt.value, END]
        )
    graph.add_conditional_edges(
        AgentName.healer.value, route_after_healer, [AgentName.provisioner.value, END]
    )
    return graph.compile()


async def run_deployment(
    graph: CompiledStateGraph, repo_url: str, emit: EmitFn = _discard
) -> DeploymentState:
    """Run the pipeline to completion and return the final state."""
    result = await graph.ainvoke(
        DeploymentState(repo_url=repo_url),
        config={"configurable": {"emit": emit}},
    )
    return DeploymentState.model_validate(result)
