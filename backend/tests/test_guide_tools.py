import asyncio
from typing import Any

import pytest

from agents.guide import tools
from agents.guide.tools import Toolbox


async def fake_profiler(url: str) -> dict[str, Any]:
    return {"repo": url.removeprefix("https://github.com/"), "components": []}


@pytest.fixture
def box() -> Toolbox:
    return Toolbox(profiler=fake_profiler)


async def test_search_labels_sources_stably(box: Toolbox) -> None:
    first = await box.call("search_portfolio", {"query": "contact email"})
    assert first.ok and first.content["results"][0]["id"] == "S1"
    assert first.sources[0].id == "contact"
    again = await box.call("search_portfolio", {"query": "email"})
    contact = next(r for r in again.content["results"] if r["title"] == "Contact")
    assert contact["id"] == "S1"  # the same document keeps its label


async def test_search_with_no_match_says_so(box: Toolbox) -> None:
    result = await box.call("search_portfolio", {"query": "zzzz qqqq"})
    assert result.ok and result.content["results"] == []
    assert (await box.call("search_portfolio", {"query": "  "})).ok is False


async def test_open_page_navigates_and_drops_unknown_sections(box: Toolbox) -> None:
    result = await box.call("open_page", {"page": "/lab", "section": "segments"})
    assert result.actions == [{"type": "navigate", "path": "/lab", "section": "segments"}]
    loose = await box.call("open_page", {"page": "/resume", "section": "nonsense"})
    assert loose.actions[0]["section"] is None
    bad = await box.call("open_page", {"page": "/admin"})
    assert not bad.ok and "page must be one of" in bad.content["error"]


async def test_score_customer_runs_the_model_and_loads_the_lab(box: Toolbox) -> None:
    result = await box.call(
        "score_customer", {"start_from": "lost_cause", "changes": {"Contract": "Two year"}}
    )
    assert result.ok
    assert result.content["started_from"] == "lost_cause"
    kinds = [a["type"] for a in result.actions]
    assert kinds == ["navigate", "set_customer"]
    assert result.actions[1]["values"]["Contract"] == "Two year"


async def test_score_customer_reports_bad_input_to_the_model(box: Toolbox) -> None:
    result = await box.call("score_customer", {"changes": {"Contract": "Forever"}})
    assert not result.ok and "must be one of" in result.content["error"]
    result = await box.call("score_customer", {"start_from": "vip"})
    assert not result.ok


async def test_profile_repo_validates_the_url(box: Toolbox) -> None:
    ok = await box.call("profile_repo", {"repo_url": "https://github.com/acme/shop.git"})
    assert ok.ok and ok.content["repo"] == "acme/shop"
    bad = await box.call("profile_repo", {"repo_url": "https://evil.example/acme/shop"})
    assert not bad.ok


async def test_profile_repo_failures_and_timeouts_are_reported(monkeypatch) -> None:
    async def broken(url: str) -> dict[str, Any]:
        raise RuntimeError("repository not found")

    result = await Toolbox(profiler=broken).call(
        "profile_repo", {"repo_url": "https://github.com/acme/missing"}
    )
    assert not result.ok and "repository not found" in result.content["error"]

    async def slow(url: str) -> dict[str, Any]:
        await asyncio.sleep(1)
        return {}

    monkeypatch.setattr(tools, "PROFILE_TIMEOUT_S", 0.01)
    result = await Toolbox(profiler=slow).call(
        "profile_repo", {"repo_url": "https://github.com/acme/slow"}
    )
    assert not result.ok and "timed out" in result.content["error"]


async def test_unknown_tools_and_bad_arguments_never_raise(box: Toolbox) -> None:
    assert not (await box.call("rm_rf", {})).ok
    result = await box.call("open_page", {"pages": "/lab"})
    assert not result.ok and "bad arguments" in result.content["error"]


def test_every_schema_has_a_handler() -> None:
    names = {s["function"]["name"] for s in tools.SCHEMAS}
    assert names == {
        "search_portfolio",
        "open_page",
        "score_customer",
        "profile_repo",
        "describe_view",
        "start_deployment",
    }


async def test_describe_view_scores_the_customer_on_screen() -> None:
    lab_box = Toolbox(
        profiler=fake_profiler, page="/lab", view={"customer": {"Contract": "Two year"}}
    )
    result = await lab_box.call("describe_view", {})
    assert result.ok and result.content["page"] == "/lab"
    assert result.content["customer"]["Contract"] == "Two year"
    assert "risk_percentile" in result.content["model_output"]
    plain = await Toolbox(profiler=fake_profiler, page="/resume").call("describe_view", {})
    assert plain.content["sections"] and "customer" not in plain.content
    bad = Toolbox(profiler=fake_profiler, page="/lab", view={"customer": {"Contract": "Forever"}})
    assert not (await bad.call("describe_view", {})).ok


async def test_start_deployment_opens_the_deployer_on_the_new_run() -> None:
    async def deployer(url: str) -> dict[str, Any]:
        return {"id": "b" * 32, "repo": url, "mode": "test"}

    box = Toolbox(profiler=fake_profiler, deployer=deployer)
    result = await box.call("start_deployment", {"repo_url": "https://github.com/acme/shop"})
    assert result.ok and result.actions == [
        {"type": "navigate", "path": f"/deployer?run={'b' * 32}", "section": None}
    ]
    assert not (
        await Toolbox(profiler=fake_profiler).call(
            "start_deployment", {"repo_url": "https://github.com/a/b"}
        )
    ).ok
    bad = await box.call("start_deployment", {"repo_url": "https://example.com/a/b"})
    assert not bad.ok
