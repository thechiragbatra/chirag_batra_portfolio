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
    configured_models,
    retry_after,
)


def sse(*events: dict) -> bytes:
    lines = [f"data: {json.dumps(e)}\n\n" for e in events] + ["data: [DONE]\n\n"]
    return "".join(lines).encode()


async def no_sleep(_: float) -> None:
    return None


def chat(handler, fallbacks: list[str] | None = None) -> GroqChat:
    return GroqChat(
        api_key="test-key",
        model="openai/gpt-oss-120b",
        transport=httpx.MockTransport(handler),
        fallbacks=fallbacks or [],
        sleep=no_sleep,
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
    assert chunks[-1] == Completion(text="Hello there", tool_calls=[], model="openai/gpt-oss-120b")
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
    with pytest.raises(LLMError) as info:
        await collect(chat(lambda r: httpx.Response(401, text="bad key")))
    assert info.value.status == 401

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


def ok_stream(text: str) -> httpx.Response:
    return httpx.Response(200, content=sse({"choices": [{"delta": {"content": text}}]}))


async def test_short_rate_limit_waits_and_retries_the_same_model() -> None:
    calls: list[str] = []
    waits: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content)["model"])
        if len(calls) == 1:
            return httpx.Response(429, text="Please try again in 1.5s.")
        return ok_stream("hi")

    async def record(seconds: float) -> None:
        waits.append(seconds)

    model = chat(handler)
    model._sleep = record
    chunks = await collect(model)
    assert calls == ["openai/gpt-oss-120b", "openai/gpt-oss-120b"]
    assert waits == [1.75] and chunks[-1].text == "hi"


async def test_exhausted_or_unknown_models_fall_back_to_the_next() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        model = json.loads(request.content)["model"]
        calls.append(model)
        if model == "openai/gpt-oss-120b":
            return httpx.Response(429, text="tokens per day (TPD): Please try again in 21m3.2s.")
        if model == "retired/model":
            return httpx.Response(404, text='{"error": {"code": "model_not_found"}}')
        return ok_stream("from the fallback")

    model = chat(handler, fallbacks=["retired/model", "openai/gpt-oss-20b"])
    chunks = await collect(model)
    assert calls == ["openai/gpt-oss-120b", "retired/model", "openai/gpt-oss-20b"]
    assert chunks[-1].text == "from the fallback"
    assert model.model == "openai/gpt-oss-20b"


async def test_errors_after_streaming_started_are_not_retried() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        body = 'data: {"choices": [{"delta": {"content": "half"}}]}\n\ndata: {"error": "boom"}\n\n'
        return httpx.Response(200, content=body.encode())

    with pytest.raises(LLMError, match="boom"):
        await collect(chat(handler, fallbacks=["openai/gpt-oss-20b"]))
    assert len(calls) == 1  # the visitor already saw "half": never start over


def test_retry_after_parses_groq_hints() -> None:
    assert retry_after("Please try again in 1.005s. Need more") == 1.005
    assert retry_after("Please try again in 397.5ms.") == 0.3975
    assert retry_after("Please try again in 21m3.2s.") == 21 * 60 + 3.2
    assert retry_after("slow down") is None


def test_configured_models(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_MODEL", "a/model")
    monkeypatch.delenv("GROQ_FALLBACK_MODELS", raising=False)
    assert configured_models() == ["a/model", "openai/gpt-oss-20b", "qwen/qwen3.8-27b"]
    monkeypatch.setenv("GROQ_FALLBACK_MODELS", "")
    assert configured_models() == ["a/model"]
    monkeypatch.setenv("GROQ_FALLBACK_MODELS", "b/model, a/model")
    assert configured_models() == ["a/model", "b/model"]
