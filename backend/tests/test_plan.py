import pytest

from agents.models import Component, Platform, RepoProfile
from agents.skills.plan import build_plan, choose_platform


def component(name: str, kind: str, framework: str | None) -> Component:
    return Component(name=name, kind=kind, path=".", framework=framework)


def profile(*components: Component, env_vars: list[str] | None = None) -> RepoProfile:
    return RepoProfile(
        name="acme/x", default_branch="main", languages=[], frameworks=[],
        components=list(components), env_vars=env_vars or [],
    )  # fmt: skip


@pytest.mark.parametrize(
    ("kind", "framework", "platform"),
    [
        ("frontend", "vite", Platform.vercel),
        ("frontend", "next", Platform.vercel),
        ("frontend", "nuxt", Platform.netlify),
        ("frontend", "static", Platform.cloudflare_pages),
        ("backend", "fastapi", Platform.render),
        ("backend", "express", Platform.render),
        ("backend", "docker", Platform.render),
        ("backend", "streamlit", Platform.hf_spaces),
        ("backend", "gradio", Platform.hf_spaces),
        ("database", "postgres", Platform.neon),
        ("database", "sqlite", Platform.turso),
    ],
)
def test_choose_platform(kind: str, framework: str, platform: Platform) -> None:
    choice = choose_platform(component("c", kind, framework))
    assert choice is not None and choice[0] is platform


def test_unsupported_database_is_skipped_with_note() -> None:
    plan = build_plan(profile(component("api", "backend", "express"),
                              component("db", "database", "mongodb")))  # fmt: skip
    assert [t.component for t in plan.targets] == ["api"]
    assert any("No free-tier target for mongodb" in n for n in plan.notes)
    assert plan.targets[0].env_vars == []  # no placed database, so no DATABASE_URL added


def test_env_vars_split_between_frontend_and_backend() -> None:
    plan = build_plan(
        profile(
            component("web", "frontend", "vite"),
            component("api", "backend", "fastapi"),
            component("db", "database", "postgres"),
            env_vars=["VITE_API_URL", "SECRET_KEY"],
        )
    )
    env = {t.component: t.env_vars for t in plan.targets}
    assert env == {"web": ["VITE_API_URL"], "api": ["SECRET_KEY", "DATABASE_URL"], "db": []}
    assert any("Render" in n for n in plan.notes)


def test_nothing_placeable_raises() -> None:
    with pytest.raises(ValueError, match="free-tier"):
        build_plan(profile(component("db", "database", "mysql")))
