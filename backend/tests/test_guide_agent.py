from typing import Any

from guide_fakes import ScriptedModel, Turn

from agents.guide import agent as guide
from agents.guide.agent import build_guide, route_after_model, run_guide, summarize
from agents.guide.tools import Toolbox, ToolResult


async def no_profiler(url: str) -> dict[str, Any]:
    raise AssertionError("not expected")


async def run(model: ScriptedModel, question: str = "Has he done causal inference?"):
    events: list[dict[str, Any]] = []

    async def emit(event: dict[str, Any]) -> None:
        events.append(event)

    outcome = await run_guide(
        build_guide(),
        [{"role": "user", "content": question}],
        "/lab",
        model,
        Toolbox(profiler=no_profiler),
        emit,
    )
    return outcome.answer, events


async def test_search_then_answer_emits_steps_sources_and_tokens() -> None:
    model = ScriptedModel(
        Turn(calls=[("search_portfolio", {"query": "causal inference uplift"})]),
        Turn(text="Yes, he built a T-learner uplift model [S1]."),
    )
    answer, events = await run(model)
    assert answer == "Yes, he built a T-learner uplift model [S1]."
    types = [e["type"] for e in events]
    assert types[0] == "step" and events[0]["tool"] == "search_portfolio"
    assert "source" in types and types.index("source") < types.index("step_done")
    assert types[-1] == "suggestions" and types[-2] == "token"
    assert "".join(e["text"] for e in events if e["type"] == "token").strip() == answer
    # The tool result went back to the model as a tool message.
    second_call_messages = model.seen[1][0]
    assert second_call_messages[-1]["role"] == "tool"
    assert (
        second_call_messages[0]["role"] == "system" and "/lab" in second_call_messages[0]["content"]
    )


async def test_actions_are_forwarded_to_the_browser() -> None:
    model = ScriptedModel(
        Turn(calls=[("open_page", {"page": "/lab", "section": "segments"})]),
        Turn(text="Here is the segment table."),
    )
    _, events = await run(model)
    action = next(e["action"] for e in events if e["type"] == "action")
    assert action == {"type": "navigate", "path": "/lab", "section": "segments"}


async def test_text_before_a_tool_call_is_reset() -> None:
    model = ScriptedModel(
        Turn(text="Let me check.", calls=[("search_portfolio", {"query": "fraud"})]),
        Turn(text="RADAR detects fraud [S1]."),
    )
    _, events = await run(model)
    types = [e["type"] for e in events]
    assert types.index("reset_text") < types.index("step")


async def test_the_last_round_runs_without_tools() -> None:
    looping = [Turn(calls=[("search_portfolio", {"query": "x"})])] * guide.MAX_TOOL_ROUNDS
    model = ScriptedModel(*looping, Turn(text="Final answer."))
    answer, _ = await run(model)
    assert answer == "Final answer."
    assert model.seen[-1][1] is None  # no tools offered on the final round
    assert all(tools is not None for _, tools in model.seen[:-1])


async def test_malformed_tool_arguments_become_a_tool_error() -> None:
    model = ScriptedModel(Turn(calls=[("open_page", {})]), Turn(text="Sorry."))
    _, events = await run(model)
    done = next(e for e in events if e["type"] == "step_done")
    assert done["ok"] is False


def test_route_after_model() -> None:
    assert (
        route_after_model({"messages": [{"role": "assistant", "tool_calls": [{}]}], "rounds": 0})
        == "tools"
    )
    assert (
        route_after_model({"messages": [{"role": "assistant", "content": "hi"}], "rounds": 0})
        != "tools"
    )


def test_summaries_are_short_and_informative() -> None:
    assert summarize("search_portfolio", ToolResult({"results": [{}, {}]})) == "2 sources"
    assert (
        summarize("open_page", ToolResult({"opened": "/lab", "section": "risk"}))
        == "opened /lab · risk"
    )
    scored = ToolResult(
        {"risk_percentile": 90.2, "segment": "lost_cause", "offer_effect_points": 0.8}
    )
    assert (
        summarize("score_customer", scored) == "90th percentile risk · lost cause · offer +0.8 pts"
    )
    assert summarize("open_page", ToolResult({"error": "nope"}, ok=False)) == "nope"


async def test_invisible_characters_are_stripped_from_answers() -> None:
    model = ScriptedModel(Turn(text="He knows causal inference [​S1]."))
    answer, events = await run(model)
    assert answer == "He knows causal inference [S1]."
    assert "​" not in "".join(e["text"] for e in events if e["type"] == "token")


async def test_show_me_opens_the_cited_page_when_the_model_does_not() -> None:
    model = ScriptedModel(
        Turn(calls=[("search_portfolio", {"query": "fraud detection"})]),
        Turn(text="RADAR detects fraud in real time [S1]."),
    )
    _, events = await run(model, question="Show me his fraud detection project")
    actions = [e["action"] for e in events if e["type"] == "action"]
    assert actions and actions[0]["type"] == "navigate"


async def test_no_auto_open_without_show_intent_or_when_already_navigated() -> None:
    model = ScriptedModel(
        Turn(calls=[("search_portfolio", {"query": "fraud"})]),
        Turn(text="RADAR detects fraud [S1]."),
    )
    _, events = await run(model, question="What does RADAR do?")
    assert not [e for e in events if e["type"] == "action"]
    model = ScriptedModel(
        Turn(calls=[("open_page", {"page": "/resume", "section": "skills"})]),
        Turn(text="Here are his skills."),
    )
    _, events = await run(model, question="Show me his skills")
    assert len([e for e in events if e["type"] == "action"]) == 1


async def test_answers_end_with_follow_up_suggestions() -> None:
    model = ScriptedModel(
        Turn(calls=[("search_portfolio", {"query": "churn uplift"})]),
        Turn(text="He built a churn uplift model [S1][S2]."),
    )
    _, events = await run(model, question="Tell me about his churn project")
    suggestions = events[-1]
    assert suggestions["type"] == "suggestions" and 1 <= len(suggestions["items"]) <= 3
