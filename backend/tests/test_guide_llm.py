import json

import httpx
import pytest

from agents.guide.llm import (
    Completion,
    GroqChat,
    LLMError,
    TextDelta,
    ToolCall,
    accumulate_tool_calls,
)


def sse(*events: dict) -> bytes:
    lines = [f"data: {json.dumps(e)}\n\n" for e in events] + ["data: [DONE]\n\n"]
    return "".join(lines).encode()


def chat(handler) -> GroqChat:
    return GroqChat(
        api_key="test-key", model="openai/gpt-oss-120b", transport=httpx.MockTransport(handler)
    )


async def collect(model: GroqChat):
    return [c async for c in model.stream([{"role": "user", "content": "hi"}], tools=[{"x": 1}])]


async def test_streams_text_and_sends_the_right_request() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            content=sse(
                {"choices": [{"delta": {"content": "Hello "}}]},
                {"choices": [{"delta": {"content": "there"}}]},
            ),
        )

    chunks = await collect(chat(handler))
    assert [c.text for c in chunks if isinstance(c, TextDelta)] == ["Hello ", "there"]
    assert chunks[-1] == Completion(text="Hello there", tool_calls=[])
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"]["stream"] is True and seen["body"]["tool_choice"] == "auto"
    assert seen["body"]["reasoning_effort"] == "low"


async def test_assembles_streamed_tool_calls() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        fragments = [
            {
                "index": 0,
                "id": "call_1",
                "function": {"name": "search_portfolio", "arguments": '{"qu'},
            },
            {"index": 0, "function": {"arguments": 'ery": "rag"}'}},
        ]
        return httpx.Response(
            200, content=sse(*({"choices": [{"delta": {"tool_calls": [f]}}]} for f in fragments))
        )

    final = (await collect(chat(handler)))[-1]
    assert final.tool_calls == [ToolCall("call_1", "search_portfolio", '{"query": "rag"}')]
    assert final.tool_calls[0].parsed() == {"query": "rag"}


async def test_rate_limits_and_outages_raise_llm_error() -> None:
    with pytest.raises(LLMError) as info:
        await collect(chat(lambda r: httpx.Response(429, text="slow down")))
    assert info.value.status == 429

    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    with pytest.raises(LLMError, match="unreachable"):
        await collect(chat(down))


def test_accumulate_handles_parallel_calls() -> None:
    calls: dict = {}
    accumulate_tool_calls(
        calls, [{"index": 1, "id": "b", "function": {"name": "open_page", "arguments": "{}"}}]
    )
    accumulate_tool_calls(
        calls, [{"index": 0, "id": "a", "function": {"name": "search_portfolio"}}]
    )
    assert sorted(calls) == [0, 1] and calls[1]["name"] == "open_page"


def test_parsed_tolerates_bad_json() -> None:
    assert ToolCall("x", "open_page", "{not json").parsed() == {}
    assert ToolCall("x", "open_page", "[1, 2]").parsed() == {}


def test_missing_key_is_an_error(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        GroqChat()
