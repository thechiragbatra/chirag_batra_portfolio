import time

from app.services.guide_store import AnswerCache, RunLog, RunRecord, normalize_question


def record(i: int, **kw) -> RunRecord:
    return RunRecord(id=f"{i:032x}", started=time.time(), page="/projects", question=f"q{i}", **kw)


def test_stats_aggregate_without_text() -> None:
    log = RunLog()
    log.add(
        record(
            1,
            latency_ms=900,
            models=["m1", "m1"],
            prompt_tokens=1000,
            completion_tokens=100,
            tools=["search_portfolio"],
        )
    )
    log.add(record(2, latency_ms=100, cached=True))
    log.add(record(3, ok=False, latency_ms=50))
    stats = log.stats()
    assert stats["questions"] == 3 and stats["answered_from_cache"] == 1 and stats["errors"] == 1
    assert stats["models"] == {"m1": 1}
    assert stats["tokens"] == {"prompt": 1000, "completion": 100}
    assert stats["tokens_per_answer"] == 1100
    assert stats["latency_ms"]["p50"] == 900
    assert "q1" not in str(stats)


def test_old_records_leave_the_window_and_the_log_is_bounded() -> None:
    log = RunLog(max_records=2)
    for i in range(3):
        log.add(record(i))
    assert len(log.records) == 2 and log.get(f"{0:032x}") is None
    assert log.stats(now=time.time() + 2 * 86400)["questions"] == 0


def test_cache_keys_ignore_case_and_punctuation_and_expire() -> None:
    cache = AnswerCache(ttl_s=60)
    events = [{"type": "token", "text": "hi"}]
    assert cache.put("Who is Chirag?", "/projects", events, ["search_portfolio"])
    assert cache.get("who is chirag", "/projects") == events
    assert cache.get("who is chirag", "/lab") is None
    assert cache.get("who is chirag", "/projects", now=time.time() + 61) is None
    assert normalize_question("  What's   his GPA?! ") == "what s his gpa"


def test_cache_refuses_live_or_failed_answers() -> None:
    cache = AnswerCache()
    assert not cache.put("q", "/p", [], ["profile_repo"])
    assert not cache.put("q", "/p", [{"type": "error", "message": "x"}], [])
