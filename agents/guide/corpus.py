"""What the guide knows: the portfolio's own content, split into citable documents.

Everything comes from the files the site itself renders (frontend/src/data/*.json and the
Churn Lab bundle), so the guide can never know more, or other, than the site says.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def portfolio_dir() -> Path:
    """The frontend directory holding src/data and public/models (PORTFOLIO_DIR overrides)."""
    return Path(os.getenv("PORTFOLIO_DIR") or REPO_ROOT / "frontend")


@dataclass(frozen=True)
class Doc:
    id: str
    title: str
    text: str
    # Where the site shows it: a route plus an optional section the page can highlight.
    page: str
    section: str | None = None
    url: str | None = None  # external source (repo, design doc)


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# Site-level facts no JSON file holds: what the pages are and how the platform works.
SITE_DOCS: tuple[Doc, ...] = (
    Doc(
        id="site-overview",
        title="About this site",
        page="/projects",
        text=(
            "This site is Chirag Batra's portfolio and doubles as DeploySmith OS, a multi-agent "
            "deployment platform he built. Pages: Projects (selected work and projects being "
            "built), Lab (the Churn Uplift Lab, live ML models in the browser), Resume, Deployer "
            "(paste a GitHub repo and watch four agents profile, plan, deploy and health-check it) "
            "and Apps (apps deployed by the local sandbox engine). This guide is an AI agent built "
            "with LangGraph that answers from the site's own content and can use the site's tools."
        ),
    ),
    Doc(
        id="deploysmith-pipeline",
        title="How DeploySmith deploys a repository",
        page="/deployer",
        url="https://github.com/thechiragbatra/deploysmith",
        text=(
            "DeploySmith runs four LangGraph agents. The profiler shallow-clones a public GitHub "
            "repo with hardened git settings and analyzes it statically, never executing its code. "
            "The strategist plans free-tier hosting for each component: Vercel, Netlify or "
            "Cloudflare Pages for frontends, Render or Hugging Face Spaces for backends, Neon, "
            "Supabase or Turso for databases, or the local sandbox engine. The provisioner deploys "
            "and the healer probes each URL, diagnoses failures and can send the run back for up "
            "to "
            "three repairs. Every step streams to the browser over server-sent events."
        ),
    ),
    Doc(
        id="deploysmith-sandbox",
        title="The DeploySmith sandbox engine",
        page="/apps",
        url="https://github.com/thechiragbatra/deploysmith",
        text=(
            "The sandbox engine is a $0 Vercel/Render-style deployment engine on a local machine. "
            "Repo code runs only inside hardened Docker containers: non-root, all Linux "
            "capabilities dropped, no-new-privileges, read-only root filesystem, memory, CPU and "
            "process limits, network only for dependency installs, no network during builds and an "
            "internal-only network at runtime. An nginx router serves each app at "
            "<app>.localhost. Deploys are immutable, with build logs, health checks and one-click "
            "rollback. It powers real deploys of static sites, Next.js, Express, FastAPI, Flask "
            "and Streamlit apps. The hosted copy of the site simulates this final step because "
            "Cloud Run has no Docker daemon."
        ),
    ),
)


def _resume_docs(resume: dict[str, Any]) -> list[Doc]:
    basics = resume["basics"]
    links = ", ".join(
        f"{link['label']}: {link['url'].removeprefix('mailto:')}" for link in basics["links"]
    )
    docs = [
        Doc(
            id="resume-summary",
            title="Résumé summary",
            page="/resume",
            text=f"{basics['name']}, {basics['title']}, {basics['location']}. {basics['summary']}",
        ),
        Doc(id="contact", title="Contact", page="/resume", text=f"Contact Chirag Batra. {links}."),
    ]
    for i, job in enumerate(resume["experience"]):
        docs.append(
            Doc(
                id=f"experience-{i + 1}",
                title=f"{job['role']} at {job['company']}",
                page="/resume",
                section="experience",
                text=(
                    f"{job['role']} at {job['company']} ({job['location']}), {job['start']} to "
                    f"{job['end']}. " + " ".join(job["highlights"])
                ),
            )
        )
    for i, school in enumerate(resume["education"]):
        docs.append(
            Doc(
                id=f"education-{i + 1}",
                title=f"Education: {school['school']}",
                page="/resume",
                section="education",
                text=(
                    f"{school['degree']}, {school['school']}, "
                    f"{school['start']} to {school['end']}. "
                    f"{school.get('details') or ''}"
                ).strip(),
            )
        )
    docs.append(
        Doc(
            id="certifications",
            title="Certifications",
            page="/resume",
            section="education",
            text="Certifications: " + "; ".join(resume["certifications"]) + ".",
        )
    )
    for group in resume["skills"]:
        slug = group["category"].lower().replace(" & ", "-").replace(" ", "-")
        docs.append(
            Doc(
                id=f"skills-{slug}",
                title=f"Skills: {group['category']}",
                page="/resume",
                section="skills",
                text=f"{group['category']} skills: " + ", ".join(group["items"]) + ".",
            )
        )
    for i, project in enumerate(resume["projects"]):
        docs.append(
            Doc(
                id=f"resume-project-{i + 1}",
                title=f"Résumé project: {project['name']}",
                page="/resume",
                url=project.get("url"),
                text=(
                    f"{project['name']}: {project['description']} "
                    f"Tech: {', '.join(project['tech'])}."
                ),
            )
        )
    return docs


def _project_docs(projects: list[dict[str, Any]], planned: list[dict[str, Any]]) -> list[Doc]:
    docs = [
        Doc(
            id=f"project-{i + 1}",
            title=project["title"],
            page=project.get("demo") or "/projects",
            section=None if project.get("demo") else "projects",
            url=project["githubUrl"],
            text=(
                f"{project['title']} (built project): {project['description']} "
                f"Tags: {', '.join(project['tags'])}."
                + (" It has a live interactive demo on this site." if project.get("demo") else "")
            ),
        )
        for i, project in enumerate(projects)
    ]
    docs += [
        Doc(
            id=f"planned-{i + 1}",
            title=f"{project['title']} (planned, not built yet)",
            page="/projects",
            section="building",
            url=project.get("designDocUrl"),
            text=(
                f"{project['title']} is a PLANNED project: designed and scoped with a design doc, "
                f"but not built yet, so it has no results. Focus: {project['focus']}. "
                f"{project['summary']} Planned stack: {', '.join(project['tags'])}."
            ),
        )
        for i, project in enumerate(planned)
    ]
    return docs


def _highlight_doc(highlights: list[dict[str, Any]]) -> Doc:
    parts = [
        f"{h.get('prefix', '')}{h['value']}{h.get('suffix', '')} {h['label']}" for h in highlights
    ]
    return Doc(
        id="highlights",
        title="Headline numbers",
        page="/projects",
        section="hero",
        text="Headline numbers on the home page: " + "; ".join(parts) + ".",
    )


def _lab_docs(lab: dict[str, Any]) -> list[Doc]:
    m = lab["churn"]["metrics"]
    u = lab["uplift"]
    seg = u["segments"]
    pct = lambda v: f"{v * 100:.0f}%"  # noqa: E731
    return [
        Doc(
            id="lab-overview",
            title="Churn Uplift Lab",
            page="/lab",
            url="https://github.com/thechiragbatra/deploysmith/tree/main/ml/churn",
            text=(
                "The Churn Uplift Lab runs the churn project's models live in the browser: an "
                f"XGBoost churn model ({len(lab['churn']['model']['trees'])} trees) with exact "
                "TreeSHAP explanations computed in TypeScript and checked against XGBoost, and a "
                "T-learner uplift model that decides whether a retention offer is worth sending. "
                "Customers are segmented as persuadable (send the offer), sure thing (stays "
                "anyway), "
                "lost cause (leaves anyway) or sleeping dog (the offer backfires)."
            ),
        ),
        Doc(
            id="lab-churn-eval",
            title="Churn Lab: churn model evaluation",
            page="/lab",
            section="evaluation",
            text=(
                f"The churn model reaches ROC-AUC {m['auc']:.3f} on the project's own holdout "
                "split "
                f"and {m['aucSplits']['mean']:.3f} ± {m['aucSplits']['sd']:.3f} over "
                f"{m['aucSplits']['n']} random splits, with recall {pct(m['recall'])} and "
                "precision "
                f"{pct(m['precision'])} at a 0.5 threshold. It is trained with SMOTE, so the lab "
                "shows risk as a percentile rather than a probability."
            ),
        ),
        Doc(
            id="lab-uplift-eval",
            title="Churn Lab: uplift benchmark results",
            page="/lab",
            section="evaluation",
            text=(
                "On the semi-synthetic benchmark (mean of "
                f"{len(u['seeds'])} simulated experiments), targeting the top 20% of customers by "
                f"predicted uplift prevents {pct(u['gainAt20']['mean'])} more churn than targeting "
                "by "
                f"churn risk, or matches it with {pct(u['offersSavedAt20']['mean'])} fewer offers. "
                f"Predicted and true effects correlate at {u['correlation']['mean']:.2f}; "
                f"{pct(u['segmentAccuracy'])} of customers land in their true segment (chance "
                "about "
                f"29%); one customer's effect is typically off by ±{u['errorSd'] * 100:.0f} "
                "points, "
                "so the model is used for ranking who gets offers, not individual promises. True "
                "average effect by predicted segment: persuadable "
                f"{seg['persuadable']['trueEffect'] * 100:.1f} "
                f"points saved, sleeping dog {abs(seg['sleeping_dog']['trueEffect']) * 100:.1f} "
                "points "
                "of extra churn."
            ),
        ),
        Doc(
            id="lab-method",
            title="Churn Lab: method and caveats",
            page="/lab",
            section="method",
            text=(
                "The Telco dataset has no record of retention offers, so the uplift model is "
                "graded "
                "on a semi-synthetic benchmark: real customers, a planted offer effect, and a "
                "simulated 50/50 randomized experiment. Planted effect: month-to-month customers "
                "respond, most around a year in and more on high bills; new fiber customers "
                "without "
                "tech support are lost causes; long-tenure customers on automatic payment are "
                "sleeping dogs. Before real use the offer needs an actual A/B test."
            ),
        ),
    ]


@lru_cache(maxsize=4)
def _load(root: str) -> tuple[Doc, ...]:
    base = Path(root)
    data = base / "src" / "data"
    docs: list[Doc] = list(SITE_DOCS)
    docs += _resume_docs(_read(data / "resume.json"))
    docs += _project_docs(_read(data / "projects.json"), _read(data / "planned.json"))
    docs.append(_highlight_doc(_read(data / "highlights.json")))
    lab = base / "public" / "models" / "churn-lab.json"
    if lab.exists():
        docs += _lab_docs(_read(lab))
    ids = [d.id for d in docs]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate document ids in the guide corpus")
    return tuple(docs)


def load_corpus(root: Path | None = None) -> tuple[Doc, ...]:
    return _load(str(root or portfolio_dir()))
