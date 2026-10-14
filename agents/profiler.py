"""Profiler: inspects a repository statically and describes what it contains.

Mock: derives the repo name from the URL and returns a typical React + FastAPI
monorepo profile. The real version will shallow-clone and analyze files only;
it must never execute code from the target repo.
"""

from __future__ import annotations

from agents.base import AgentUpdate, LogFn, mock_pause
from agents.models import AgentName, Component, DeploymentState, LogLevel, RepoProfile


def repo_name_from_url(repo_url: str) -> str:
    """'https://github.com/acme/shop.git' -> 'acme/shop'."""
    path = repo_url.rstrip("/").removesuffix(".git")
    owner, repo = path.split("/")[-2:]
    return f"{owner}/{repo}"


class MockProfiler:
    name = AgentName.profiler

    async def run(self, state: DeploymentState, log: LogFn) -> AgentUpdate:
        name = repo_name_from_url(state.repo_url)
        await log(f"Shallow-cloning {name} (depth=1, static analysis only)")
        await mock_pause()
        await log("Scanning manifests: package.json, pyproject.toml, Dockerfile")
        await mock_pause()
        await log("Detected frontend/ (Vite + React) and api/ (FastAPI)")
        await log("Found DATABASE_URL in api/.env.example", LogLevel.warn)
        await mock_pause(0.5)

        profile = RepoProfile(
            name=name,
            default_branch="main",
            languages=["TypeScript", "Python"],
            frameworks=["React", "Vite", "FastAPI"],
            components=[
                Component(
                    name="web",
                    kind="frontend",
                    path="frontend",
                    framework="vite",
                    build_command="npm run build",
                ),
                Component(
                    name="api",
                    kind="backend",
                    path="api",
                    framework="fastapi",
                    start_command="uvicorn main:app --host 0.0.0.0 --port $PORT",
                    port=8000,
                ),
                Component(name="db", kind="database", path="api/migrations", framework="postgres"),
            ],
            env_vars=["DATABASE_URL", "VITE_API_URL"],
        )
        await log(f"Profile complete: {len(profile.components)} components", LogLevel.success)
        return {"repo_profile": profile}
