"""How the sandbox engine installs, builds and runs each supported framework.

A recipe is data: the image and the shell commands for each step. The commands
are fixed templates plus values from the static analysis (agents/skills/analyze.py),
and they only ever run inside a sandbox container (agents/sandbox/docker.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from agents.models import Component
from agents.sandbox.docker import NODE_IMAGE, PYTHON_IMAGE, WORKDIR

APP_PORT = 8000

# Frameworks whose build emits static files (served by the router, no process).
STATIC_BUILDS = frozenset(
    {"vite", "create-react-app", "vue-cli", "parcel", "astro", "angular", "webpack"}
)
NODE_SERVERS = frozenset({"express", "fastify", "koa", "hono", "nestjs", "next"})
PYTHON_SERVERS = frozenset({"fastapi", "flask", "django", "streamlit", "gradio"})
SUPPORTED = STATIC_BUILDS | NODE_SERVERS | PYTHON_SERVERS | {"static"}

# The WSGI/ASGI server each start command needs, installed even if the repo forgot it.
_PYTHON_SERVER_PACKAGE = {"fastapi": "uvicorn", "flask": "gunicorn", "django": "gunicorn"}
OUTPUT_DIRS = ("dist", "build", "out", "public")
_SAFE_PATH = re.compile(r"^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$")


class UnsupportedComponent(ValueError):
    """The sandbox has no recipe for this component."""


@dataclass(frozen=True)
class Recipe:
    mode: Literal["static", "server"]
    image: str
    workdir: str
    install: str | None = None
    build: str | None = None
    start: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    # Only for the running app. NODE_ENV=production during install would make npm skip
    # devDependencies (typescript, next build tooling), breaking the build step.
    run_env: dict[str, str] = field(default_factory=dict)


def component_workdir(component: Component) -> str:
    if component.path == ".":
        return WORKDIR
    if not _SAFE_PATH.match(component.path) or ".." in component.path.split("/"):
        raise UnsupportedComponent(f"unsafe component path: {component.path!r}")
    return f"{WORKDIR}/{component.path}"


def _node_runner(command: str) -> str:
    """pnpm and yarn come from corepack (bundled with Node), cached inside /app."""
    first, _, rest = command.partition(" ")
    if first in {"pnpm", "yarn"}:
        return f"corepack {first} {rest}".strip()
    return command


def _node_install(command: str | None, has_lockfile: bool) -> str:
    runner = (command or "npm").split(" ", 1)[0]
    if runner == "pnpm":
        return "corepack pnpm install --frozen-lockfile"
    if runner == "yarn":
        return "corepack yarn install"
    return "npm ci --no-audit --no-fund" if has_lockfile else "npm install --no-audit --no-fund"


_NODE_ENV = {
    "npm_config_cache": "/tmp/.npm",
    "npm_config_update_notifier": "false",
    "COREPACK_HOME": f"{WORKDIR}/.deploysmith/corepack",
    "COREPACK_ENABLE_DOWNLOAD_PROMPT": "0",
    "NEXT_TELEMETRY_DISABLED": "1",
    "ASTRO_TELEMETRY_DISABLED": "1",
}


def recipe_for(component: Component, has_lockfile: bool = False) -> Recipe:
    """The recipe for a component, or UnsupportedComponent with the reason."""
    framework = component.framework or ""
    if component.kind == "database":
        raise UnsupportedComponent("databases are not provisioned by the sandbox engine")
    if framework not in SUPPORTED:
        raise UnsupportedComponent(f"no sandbox recipe for {framework or component.kind}")
    workdir = component_workdir(component)

    if framework == "static":
        return Recipe(mode="static", image=NODE_IMAGE, workdir=workdir)

    if framework in STATIC_BUILDS or framework in NODE_SERVERS:
        install = _node_install(component.build_command, has_lockfile)
        build = _node_runner(component.build_command) if component.build_command else None
        if framework in STATIC_BUILDS:
            if build is None:
                raise UnsupportedComponent(f"{framework} app has no build script")
            return Recipe("static", NODE_IMAGE, workdir, install, build, env=dict(_NODE_ENV))
        if not component.start_command:
            raise UnsupportedComponent(f"{framework} app has no start script")
        start = _node_runner(component.start_command)
        run_env = {"NODE_ENV": "production", "HOST": "0.0.0.0"}
        return Recipe(
            "server", NODE_IMAGE, workdir, install, build, start, dict(_NODE_ENV), run_env
        )

    # Python servers: a venv inside the deploy copy, so the run container sees it too.
    if not component.start_command:
        raise UnsupportedComponent(f"no entry point found for the {framework} app")
    extra = _PYTHON_SERVER_PACKAGE.get(framework, "")
    install = (
        "python -m venv .venv && "
        "if [ -f requirements.txt ]; then .venv/bin/pip install -r requirements.txt; "
        "else .venv/bin/pip install .; fi"
    )
    if extra:
        install += f" && .venv/bin/pip install {extra}"
    env = {
        "PIP_NO_CACHE_DIR": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PATH": f"{workdir}/.venv/bin:/usr/local/bin:/usr/bin:/bin",
        "GRADIO_SERVER_NAME": "0.0.0.0",
        "GRADIO_SERVER_PORT": str(APP_PORT),
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
    }
    return Recipe("server", PYTHON_IMAGE, workdir, install, None, component.start_command, env)
