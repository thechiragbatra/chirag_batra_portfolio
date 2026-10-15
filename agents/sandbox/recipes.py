"""How the sandbox engine installs, builds and runs each supported framework.

A recipe is data: the image and the shell commands for each step. The commands
are fixed templates plus values from the static analysis (agents/skills/analyze.py),
and they only ever run inside a sandbox container (agents/sandbox/docker.py).
"""

from __future__ import annotations

import re
import tomllib
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


# Written by the engine into the app directory when the repo declares its dependencies
# only in pyproject.toml without a build backend, so `pip install .` would fail.
GENERATED_REQUIREMENTS = ".deploysmith-requirements.txt"


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


def python_requirements(pyproject: str) -> list[str] | None:
    """Requirement lines for a pyproject with dependencies but no [build-system].

    None when `pip install .` is the right call (a build backend exists) or nothing is
    declared. Lines that look like pip options are dropped: they are data from the repo.
    """
    try:
        data = tomllib.loads(pyproject)
    except tomllib.TOMLDecodeError:
        return None
    if "build-system" in data:
        return None
    deps = [str(d) for d in data.get("project", {}).get("dependencies", [])]
    poetry = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    deps += [name for name in poetry if name.lower() != "python"]  # versions use ^/~ syntax
    lines = [d.strip() for d in deps if d.strip() and not d.strip().startswith("-")]
    return lines or None


PYTHON_MINORS = (11, 12, 13, 14)  # python:3.x-slim images the engine may pick
_LOWER = re.compile(r">=\s*3\.(\d+)")
_UPPER = re.compile(r"<\s*3\.(\d+)")


def python_image_for(pyproject: str) -> str | None:
    """The python:3.x-slim image satisfying [project].requires-python, or None to keep
    the default. Prefers the default minor when allowed, else the lowest that fits."""
    try:
        spec = str(tomllib.loads(pyproject).get("project", {}).get("requires-python", ""))
    except tomllib.TOMLDecodeError:
        return None
    if not spec:
        return None
    lower = max((int(m) for m in _LOWER.findall(spec)), default=0)
    upper = min((int(m) for m in _UPPER.findall(spec)), default=99)
    allowed = [m for m in PYTHON_MINORS if lower <= m < upper]
    default_minor = int(PYTHON_IMAGE.split(":")[1].split(".")[1].split("-")[0])
    if not allowed or default_minor in allowed:
        return None
    return f"python:3.{allowed[0]}-slim"


def _node_install(command: str | None, has_lockfile: bool) -> str:
    runner = (command or "npm").split(" ", 1)[0]
    if runner == "pnpm":
        return "corepack pnpm install --frozen-lockfile"
    if runner == "yarn":
        return "corepack yarn install"
    return "npm ci --no-audit --no-fund" if has_lockfile else "npm install --no-audit --no-fund"


# Package caches live on disk inside the build copy, not in the container's small
# in-memory /tmp (Next.js alone downloads >1 GB of platform binaries). The engine
# deletes this directory after the install step so it is never kept in a deploy.
CACHE_DIR = ".deploysmith/cache"

_NODE_ENV = {
    "npm_config_cache": f"{WORKDIR}/{CACHE_DIR}/npm",
    "YARN_CACHE_FOLDER": f"{WORKDIR}/{CACHE_DIR}/yarn",
    "npm_config_store_dir": f"{WORKDIR}/{CACHE_DIR}/pnpm",
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
        # The package manager shows in whichever script exists (a server may have no build).
        install = _node_install(component.build_command or component.start_command, has_lockfile)
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
        f"elif [ -f {GENERATED_REQUIREMENTS} ]; then "
        f".venv/bin/pip install -r {GENERATED_REQUIREMENTS}; "
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
