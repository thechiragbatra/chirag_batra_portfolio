"""The guide's tools: the site's own capabilities, exposed to the model.

Each tool returns two things: `content`, the JSON the model reads, and `actions`, what the
browser should do (navigate, highlight a section, load a customer into the Churn Lab).
Tool output is data; nothing here executes anything the model or a repo supplies.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from agents.guide import churn
from agents.guide.corpus import Doc, load_corpus
from agents.guide.search import Index
from agents.skills.github_url import normalize_github_url

# Pages the guide may open, and the sections each page marks with data-guide="...".
PAGES: dict[str, tuple[str, ...]] = {
    "/projects": ("hero", "projects", "building"),
    "/lab": ("customer", "risk", "reasons", "offer", "evaluation", "segments", "method"),
    "/resume": ("experience", "education", "projects", "skills"),
    "/deployer": (),
    "/apps": (),
}
PROFILE_TIMEOUT_S = 75.0

Action = dict[str, Any]


@dataclass
class ToolResult:
    content: dict[str, Any]
    actions: list[Action] = field(default_factory=list)
    # Documents this call surfaced, for the answer's citations.
    sources: list[Doc] = field(default_factory=list)
    ok: bool = True

    def model_text(self) -> str:
        return json.dumps(self.content, ensure_ascii=False)


class ToolError(Exception):
    """A tool was called with bad arguments; the model sees the message and can retry."""


SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_portfolio",
            "description": (
                "Search Chirag's portfolio (résumé, internships, projects, planned projects, "
                "skills, "
                "the Churn Lab results, how this site works). Returns passages with ids like S1 to "
                "cite. Call it before stating any fact about Chirag."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Keywords, e.g. 'causal inference uplift'",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_page",
            "description": (
                "Navigate the visitor's browser to a page of this site and optionally highlight a "
                "section, to show what you are describing. Pages and sections: "
                + "; ".join(f"{p}: {', '.join(s) or '(none)'}" for p, s in PAGES.items())
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {"type": "string", "enum": list(PAGES)},
                    "section": {"type": "string", "description": "Optional section of that page"},
                },
                "required": ["page"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_customer",
            "description": (
                "Run the Churn Lab models (XGBoost churn risk with SHAP reasons, T-learner offer "
                "uplift) on a telecom customer, for what-if questions. Start from a typical "
                "customer of a segment and apply changes. Also loads the customer into the Lab "
                "page "
                "so the visitor sees it. Attributes: tenure (months 1-72), MonthlyCharges "
                "(18-119), "
                "TotalCharges, Contract (Month-to-month | One year | Two year), InternetService "
                "(DSL | Fiber optic | No), PaymentMethod (Electronic check | Mailed check | Bank "
                "transfer (automatic) | Credit card (automatic)), TechSupport, OnlineSecurity, "
                "OnlineBackup, DeviceProtection, StreamingTV, StreamingMovies, PaperlessBilling, "
                "Partner, Dependents, PhoneService, MultipleLines (Yes | No), SeniorCitizen (0 | "
                "1), "
                "gender (Female | Male)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start_from": {
                        "type": "string",
                        "enum": ["persuadable", "sure_thing", "lost_cause", "sleeping_dog"],
                        "description": "Typical customer to start from (default persuadable)",
                    },
                    "changes": {
                        "type": "object",
                        "description": 'Attribute -> new value, e.g. {"Contract": "Two year"}',
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "profile_repo",
            "description": (
                "Run DeploySmith's real profiler and strategist on a public GitHub repository: a "
                "hardened shallow clone analyzed statically (nothing is executed), then a "
                "free-tier "
                "hosting plan. Use when the visitor gives a repo URL and asks what it contains or "
                "how DeploySmith would deploy it. Takes a few seconds."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "repo_url": {"type": "string", "description": "https://github.com/owner/repo"}
                },
                "required": ["repo_url"],
            },
        },
    },
]


class Toolbox:
    """Binds the tools to a corpus, a lab and a repo profiler (all swappable in tests)."""

    def __init__(
        self,
        docs: tuple[Doc, ...] | None = None,
        lab: churn.Lab | None = None,
        profiler: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
    ) -> None:
        self.docs = docs if docs is not None else load_corpus()
        self.index = Index(self.docs)
        self._lab = lab
        self.profiler = profiler or profile_github_repo
        self._cited: dict[str, str] = {}  # doc id -> citation label, stable per conversation

    @property
    def lab(self) -> churn.Lab:
        if self._lab is None:
            self._lab = churn.load_lab()
        return self._lab

    def label(self, doc: Doc) -> str:
        """Citation label (S1, S2, ...) for a document, stable for the conversation."""
        if doc.id not in self._cited:
            self._cited[doc.id] = f"S{len(self._cited) + 1}"
        return self._cited[doc.id]

    async def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        handlers = {
            "search_portfolio": self.search_portfolio,
            "open_page": self.open_page,
            "score_customer": self.score_customer,
            "profile_repo": self.profile_repo,
        }
        handler = handlers.get(name)
        if handler is None:
            return ToolResult({"error": f"unknown tool {name!r}"}, ok=False)
        try:
            return await handler(**args)
        except TypeError as exc:
            return ToolResult({"error": f"bad arguments for {name}: {exc}"}, ok=False)
        except (ToolError, churn.CustomerError) as exc:
            return ToolResult({"error": str(exc)}, ok=False)

    async def search_portfolio(self, query: str) -> ToolResult:
        if not query.strip():
            raise ToolError("query is empty")
        hits = self.index.search(query[:300], k=5)
        if not hits:
            return ToolResult({"results": [], "note": "Nothing in the portfolio matches."})
        docs = [h.doc for h in hits]
        results = [
            {"id": self.label(d), "title": d.title, "text": d.text, "page": d.page} for d in docs
        ]
        return ToolResult({"results": results}, sources=docs)

    async def open_page(self, page: str, section: str | None = None) -> ToolResult:
        if page not in PAGES:
            raise ToolError(f"page must be one of {list(PAGES)}")
        if section and section not in PAGES[page]:
            section = None  # unknown section: still navigate, just do not highlight
        action: Action = {"type": "navigate", "path": page, "section": section}
        return ToolResult({"opened": page, "section": section}, actions=[action])

    async def score_customer(
        self, start_from: str = "persuadable", changes: dict[str, Any] | None = None
    ) -> ToolResult:
        lab = self.lab
        base = lab.presets.get(start_from)
        if base is None:
            raise ToolError(f"start_from must be one of {sorted(lab.presets)}")
        changes = changes or {}
        if not isinstance(changes, dict):
            raise ToolError("changes must be an object of attribute -> value")
        customer = churn.apply_changes(lab, base, changes)
        result = churn.score(lab, customer)
        result["customer_changes"] = changes
        result["started_from"] = start_from
        actions: list[Action] = [
            {"type": "navigate", "path": "/lab", "section": "risk"},
            {"type": "set_customer", "values": customer},
        ]
        return ToolResult(result, actions=actions)

    async def profile_repo(self, repo_url: str) -> ToolResult:
        try:
            url = normalize_github_url(repo_url)
        except ValueError as exc:
            raise ToolError(str(exc)) from exc
        try:
            summary = await asyncio.wait_for(self.profiler(url), PROFILE_TIMEOUT_S)
        except TimeoutError as exc:
            raise ToolError("profiling timed out") from exc
        except Exception as exc:  # clone failures, private or missing repos
            raise ToolError(f"could not profile {url}: {exc}") from exc
        return ToolResult(summary)


async def profile_github_repo(url: str) -> dict[str, Any]:
    """Real profiler + strategist: hardened shallow clone, static analysis, free-tier plan."""
    from agents.profiler import repo_name_from_url
    from agents.skills.analyze import analyze_repo
    from agents.skills.clone import shallow_clone
    from agents.skills.plan import build_plan

    name = repo_name_from_url(url)
    async with shallow_clone(url) as checkout:
        profile = await asyncio.to_thread(analyze_repo, checkout, name)
    plan = build_plan(profile)
    return {
        "repo": name,
        "languages": profile.languages,
        "frameworks": profile.frameworks,
        "components": [
            {"name": c.name, "kind": c.kind, "path": c.path, "framework": c.framework}
            for c in profile.components
        ],
        "env_vars": profile.env_vars,
        "plan": plan.model_dump(mode="json"),
        "note": "Analyzed statically; nothing from the repo was executed.",
    }
