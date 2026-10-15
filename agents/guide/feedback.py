"""Turn thumbs-down answers into draft eval cases.

    cd backend && PYTHONPATH=.. uv run python -m agents.guide.feedback

Reads the feedback file the API appends to (GUIDE_FEEDBACK_FILE, default .guide/feedback.jsonl)
and prints one draft case per disliked answer. Review each, fill in what a good answer must
contain or cite, and add it to eval_cases.json, so the same mistake is caught next time.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from agents.guide.corpus import REPO_ROOT


def feedback_file() -> Path:
    return Path(os.getenv("GUIDE_FEEDBACK_FILE") or REPO_ROOT / ".guide" / "feedback.jsonl")


def read_feedback(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            entries.append(json.loads(line))
    return entries


def draft_cases(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One draft per distinct disliked question; the latest answer is kept for context."""
    drafts: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if entry.get("rating") != "down":
            continue
        question = entry.get("question", "").strip()
        if not question:
            continue
        drafts[question.lower()] = {
            "id": f"feedback-{entry.get('id', '')[:8]}",
            "group": "facts",
            "question": question,
            "page": entry.get("page", "/projects"),
            "_disliked_answer": entry.get("answer", ""),
            "_note": entry.get("note", ""),
            "_todo": "add cite_any / contain_any / not_match, then drop the _ fields",
        }
    return list(drafts.values())


def main() -> None:
    parser = argparse.ArgumentParser(description="Draft eval cases from thumbs-down feedback")
    parser.add_argument("--file", type=Path, default=None)
    args = parser.parse_args()
    path = args.file or feedback_file()
    drafts = draft_cases(read_feedback(path))
    if not drafts:
        print(f"No thumbs-down answers in {path}.")
        return
    print(json.dumps(drafts, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
