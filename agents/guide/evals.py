"""Evaluate Smith against a golden set of questions (agents/guide/eval_cases.json).

    cd backend && PYTHONPATH=.. uv run python -m agents.guide.evals          # needs GROQ_API_KEY
    cd backend && PYTHONPATH=.. uv run python -m agents.guide.evals --offline # skip network cases

Each case checks what matters for a portfolio guide: the right source is cited, planned
work is called planned, unknown facts are not invented, off-topic requests are declined
and the right tool is used. Results print as a table and are written to a JSON report.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.guide.agent import build_guide, run_guide
from agents.guide.llm import ChatModel
from agents.guide.tools import Toolbox

CASES_PATH = Path(__file__).with_name("eval_cases.json")


@dataclass
class Transcript:
    answer: str
    tools: list[str] = field(default_factory=list)
    cited_docs: set[str] = field(default_factory=set)


@dataclass
class Verdict:
    case: str
    group: str
    passed: bool
    failures: list[str]
    answer: str
    tools: list[str]


def load_cases(path: Path = CASES_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def grade(case: dict[str, Any], t: Transcript) -> Verdict:
    """Check one transcript against a case's expectations. Pure, so it is unit tested."""
    failures: list[str] = []
    # Models write curly quotes (isn’t); compare with straight ones.
    answer = t.answer.lower().replace("\u2019", "'").replace("\u2018", "'")
    if case.get("cite_any") and not t.cited_docs & set(case["cite_any"]):
        failures.append(
            f"cited {sorted(t.cited_docs) or 'nothing'}, wanted one of {case['cite_any']}"
        )
    if case.get("contain_any") and not any(s.lower() in answer for s in case["contain_any"]):
        failures.append(f"answer lacks any of {case['contain_any']}")
    for pattern in case.get("not_match", []):
        if re.search(pattern, t.answer, flags=re.IGNORECASE):
            failures.append(f"answer matches forbidden /{pattern}/")
    for tool in case.get("tools", []):
        # The site opening the cited page for a "show me" counts as showing it.
        shown = tool == "open_page" and "auto_open" in t.tools
        if tool not in t.tools and not shown:
            failures.append(f"did not call {tool} (called {t.tools or 'nothing'})")
    if case.get("no_tools") and any(
        n not in ("search_portfolio", "describe_view") for n in t.tools
    ):
        failures.append(f"used tools on an off-topic request: {t.tools}")
    if not t.answer.strip():
        failures.append("empty answer")
    return Verdict(case["id"], case["group"], not failures, failures, t.answer, t.tools)


async def fake_deployer(url: str) -> dict[str, Any]:
    """Evals check that Smith starts deployments, without starting real ones."""
    return {"id": "0" * 32, "repo": url, "mode": "eval (not deployed)"}


async def run_case(model: ChatModel, case: dict[str, Any], graph: Any) -> Transcript:
    page = case.get("page", "/projects")
    toolbox = Toolbox(page=page, view=case.get("view"), deployer=fake_deployer)
    outcome = await run_guide(
        graph, [{"role": "user", "content": case["question"]}], page, model, toolbox
    )
    return Transcript(
        answer=outcome.answer,
        tools=outcome.tools,
        cited_docs={d.id for d in outcome.cited},
    )


async def evaluate(
    model: ChatModel, cases: list[dict[str, Any]], pause: float = 2.0
) -> list[Verdict]:
    graph = build_guide()
    verdicts: list[Verdict] = []
    for i, case in enumerate(cases):
        if i and pause:
            await asyncio.sleep(pause)  # stay under free-tier request rates
        try:
            transcript = await run_case(model, case, graph)
            verdicts.append(grade(case, transcript))
        except Exception as exc:
            verdicts.append(Verdict(case["id"], case["group"], False, [f"error: {exc}"], "", []))
    return verdicts


def summary(verdicts: list[Verdict]) -> str:
    groups: dict[str, list[Verdict]] = {}
    for v in verdicts:
        groups.setdefault(v.group, []).append(v)
    lines = [f"{'group':<10} {'passed':>8}"]
    for group, items in groups.items():
        lines.append(f"{group:<10} {sum(v.passed for v in items):>4}/{len(items):<3}")
    total = sum(v.passed for v in verdicts)
    lines.append(f"{'total':<10} {total:>4}/{len(verdicts):<3}")
    for v in verdicts:
        if not v.passed:
            lines.append(f"  FAIL {v.case}: {'; '.join(v.failures)}")
    return "\n".join(lines)


def main() -> None:
    from agents.guide.llm import GroqChat

    parser = argparse.ArgumentParser(description="Evaluate Smith on the golden question set")
    parser.add_argument("--offline", action="store_true", help="skip cases that clone repos")
    parser.add_argument("--only", help="comma-separated case ids")
    parser.add_argument("--report", type=Path, default=Path("guide-eval-report.json"))
    parser.add_argument(
        "--pause", type=float, default=20.0, help="seconds between cases (free-tier token rate)"
    )
    args = parser.parse_args()

    cases = load_cases()
    if args.offline:
        cases = [c for c in cases if not c.get("network")]
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]

    model = GroqChat()
    started = time.monotonic()
    verdicts = asyncio.run(evaluate(model, cases, pause=args.pause))
    print(summary(verdicts))
    print(f"({time.monotonic() - started:.0f} s, model {model.model})")
    args.report.write_text(
        json.dumps([v.__dict__ for v in verdicts], indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"report: {args.report}")


if __name__ == "__main__":
    main()
