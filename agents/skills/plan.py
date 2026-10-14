"""Deterministic platform selection: each component kind/framework maps to a free tier.

Only `Platform` members can be returned, so a paid host is unrepresentable.
"""

from __future__ import annotations

from agents.models import Component, DeploymentPlan, DeploymentTarget, Platform, RepoProfile
from agents.sandbox.recipes import SUPPORTED as SANDBOX_FRAMEWORKS

SANDBOX_REASON = "Built and served by the local sandbox engine (Docker on this machine)"

# (platform, reason) for each framework; checked before the per-kind default.
_BY_FRAMEWORK: dict[str, tuple[Platform, str]] = {
    "next": (Platform.vercel, "Vercel builds Next.js natively, including server routes"),
    "nuxt": (Platform.netlify, "Netlify has a first-class Nuxt preset"),
    "sveltekit": (Platform.vercel, "SvelteKit's Vercel adapter covers SSR and static pages"),
    "static": (Platform.cloudflare_pages, "Plain static files; Cloudflare Pages serves them free"),
    "streamlit": (Platform.hf_spaces, "Hugging Face Spaces runs Streamlit apps on free CPU"),
    "gradio": (Platform.hf_spaces, "Hugging Face Spaces runs Gradio apps on free CPU"),
    "postgres": (Platform.neon, "Serverless Postgres with a free tier"),
    "sqlite": (Platform.turso, "Turso hosts SQLite-compatible databases on a free tier"),
}

_BY_KIND: dict[str, tuple[Platform, str]] = {
    "frontend": (Platform.vercel, "Static build output; Vercel's Hobby plan serves it free"),
    "backend": (Platform.render, "Long-running web server fits a Render free web service"),
}

PLATFORM_CAVEATS: dict[Platform, str] = {
    Platform.sandbox: "Sandbox apps are reachable only from this machine (http://<app>.localhost)",
    Platform.vercel: "Vercel Hobby is for non-commercial use",
    Platform.render: "Render free services sleep when idle; the first request after is slow",
    Platform.hf_spaces: "Free Spaces sleep after a period of inactivity",
    Platform.neon: "Neon free projects scale to zero and have a storage cap",
    Platform.turso: "Turso's free tier caps storage and monthly reads/writes",
}

PUBLIC_ENV_PREFIXES = ("VITE_", "NEXT_PUBLIC_", "REACT_APP_", "PUBLIC_", "NUXT_PUBLIC_")


def choose_platform(component: Component, sandbox: bool = False) -> tuple[Platform, str] | None:
    if sandbox:
        if component.kind == "database" or component.framework not in SANDBOX_FRAMEWORKS:
            return None
        return Platform.sandbox, SANDBOX_REASON
    if component.framework in _BY_FRAMEWORK:
        return _BY_FRAMEWORK[component.framework]
    return _BY_KIND.get(component.kind)


def assign_env_vars(component: Component, env_vars: list[str], has_database: bool) -> list[str]:
    """Browser-exposed vars go to frontends; everything else to backends."""
    if component.kind == "frontend":
        return [v for v in env_vars if v.startswith(PUBLIC_ENV_PREFIXES)]
    if component.kind == "backend":
        names = [v for v in env_vars if not v.startswith(PUBLIC_ENV_PREFIXES)]
        if has_database and "DATABASE_URL" not in names:
            names.append("DATABASE_URL")
        return names
    return []


def _unplaced_note(component: Component, sandbox: bool) -> str:
    what = f"{component.framework or component.kind} ({component.name})"
    if not sandbox:
        return (
            f"No free-tier target for {what}; "
            "consider migrating it to Postgres (Neon) or SQLite (Turso)"
        )
    if component.kind == "database":
        return (
            "The sandbox engine does not provision databases; "
            f"point {component.name} at your own instance"
        )
    return f"The sandbox engine has no recipe for {what}"


def build_plan(profile: RepoProfile, sandbox: bool = False) -> DeploymentPlan:
    """Map every component to a free-tier platform, or to the local sandbox engine.

    Raises ValueError if none can be placed.
    """
    targets: list[DeploymentTarget] = []
    notes: list[str] = []
    placed_database = any(
        c.kind == "database" and choose_platform(c, sandbox) is not None for c in profile.components
    )

    for component in profile.components:
        choice = choose_platform(component, sandbox)
        if choice is None:
            notes.append(_unplaced_note(component, sandbox))
            continue
        platform, reason = choice
        targets.append(
            DeploymentTarget(
                component=component.name,
                platform=platform,
                reason=reason,
                env_vars=assign_env_vars(component, profile.env_vars, placed_database),
            )
        )

    if not targets:
        where = "in the sandbox engine" if sandbox else "on a free-tier platform"
        raise ValueError(f"No component could be placed {where}")

    used = list(dict.fromkeys(t.platform for t in targets))
    notes.extend(PLATFORM_CAVEATS[p] for p in used if p in PLATFORM_CAVEATS)
    return DeploymentPlan(targets=targets, notes=notes)
