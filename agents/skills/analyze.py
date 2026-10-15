"""Static repository analysis. Reads files only; never imports or executes repo code.

Every read goes through `read_text`, which refuses symlinks, paths that escape the
root, and files over MAX_FILE_BYTES, so a hostile repo can't point us at host files
or exhaust memory.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Literal

from agents.models import Component, RepoProfile

MAX_FILE_BYTES = 256 * 1024
MAX_FILES = 20_000
MAX_COMPONENT_DEPTH = 2

SKIP_DIRS = frozenset(
    {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        "env",
        "__pycache__",
        "dist",
        "build",
        ".next",
        ".nuxt",
        ".svelte-kit",
        "vendor",
        "target",
        "coverage",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
    }
)

EXTENSION_LANGUAGES = {
    ".py": "Python",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "CSS",
}

ENV_EXAMPLE_FILES = (".env.example", ".env.sample", ".env.template", "example.env")
_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)\s*=")
_REQUIREMENT_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")

# Order matters: the first match wins (e.g. Next.js before plain React).
NODE_FRONTENDS = (
    ("next", "next"),
    ("nuxt", "nuxt"),
    ("@sveltejs/kit", "sveltekit"),
    ("astro", "astro"),
    ("@angular/core", "angular"),
    ("vite", "vite"),
    ("react-scripts", "create-react-app"),
    ("@vue/cli-service", "vue-cli"),
    ("parcel", "parcel"),
    ("webpack-dev-server", "webpack"),
)
# Bare "react"/"vue"/"svelte" without one of the tools above is a component
# library or email-template package, not a deployable site, so it is not listed.
NODE_BACKENDS = (
    ("@nestjs/core", "nestjs"),
    ("express", "express"),
    ("fastify", "fastify"),
    ("koa", "koa"),
    ("hono", "hono"),
)
PYTHON_FRAMEWORKS = ("fastapi", "django", "flask", "streamlit", "gradio")

# Dependency name -> database engine.
DATABASE_DEPENDENCIES = {
    "psycopg": "postgres",
    "psycopg2": "postgres",
    "psycopg2-binary": "postgres",
    "asyncpg": "postgres",
    "pg": "postgres",
    "postgres": "postgres",
    "@neondatabase/serverless": "postgres",
    "@supabase/supabase-js": "postgres",
    "supabase": "postgres",
    "libsql-client": "sqlite",
    "@libsql/client": "sqlite",
    "better-sqlite3": "sqlite",
    "sqlite3": "sqlite",
    "aiosqlite": "sqlite",
    "mysqlclient": "mysql",
    "pymysql": "mysql",
    "mysql2": "mysql",
    "pymongo": "mongodb",
    "motor": "mongodb",
    "mongoose": "mongodb",
    "mongodb": "mongodb",
}

DEFAULT_PORTS = {
    "fastapi": 8000,
    "flask": 8000,
    "django": 8000,
    "streamlit": 8501,
    "gradio": 7860,
}

Kind = Literal["frontend", "backend", "database"]


# --- Safe file access ------------------------------------------------------------


def read_text(root: Path, rel: str | PurePosixPath) -> str | None:
    """Read a small text file inside `root`, or None if it is unsafe or missing."""
    path = root / rel
    try:
        if path.is_symlink() or not path.is_file():
            return None
        if not path.resolve().is_relative_to(root.resolve()):
            return None
        if path.stat().st_size > MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def iter_files(root: Path, max_files: int = MAX_FILES) -> Iterator[PurePosixPath]:
    """Yield repo-relative file paths, skipping vendored dirs and all symlinks."""
    count = 0
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.is_symlink():
                continue
            if entry.is_dir():
                if entry.name not in SKIP_DIRS:
                    stack.append(entry)
            elif entry.is_file():
                yield PurePosixPath(entry.relative_to(root).as_posix())
                count += 1
                if count >= max_files:
                    return


# --- Small parsers ---------------------------------------------------------------


def parse_env_names(text: str) -> list[str]:
    """Variable names from a .env.example. Values are never kept."""
    names = (_ENV_LINE.match(line) for line in text.splitlines())
    return list(dict.fromkeys(m.group(1) for m in names if m))


def parse_requirements(text: str) -> set[str]:
    names: set[str] = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = _REQUIREMENT_NAME.match(line)
        if match:
            names.add(normalize_dep(match.group(1)))
    return names


def parse_pyproject(text: str) -> set[str]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return set()
    names: set[str] = set()
    for spec in data.get("project", {}).get("dependencies", []):
        match = _REQUIREMENT_NAME.match(str(spec))
        if match:
            names.add(normalize_dep(match.group(1)))
    poetry = data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    names.update(normalize_dep(name) for name in poetry if name.lower() != "python")
    return names


def normalize_dep(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def detect_languages(files: list[PurePosixPath], limit: int = 4) -> list[str]:
    counts = Counter(
        EXTENSION_LANGUAGES[f.suffix.lower()]
        for f in files
        if f.suffix.lower() in EXTENSION_LANGUAGES
    )
    return [language for language, _ in counts.most_common(limit)]


def default_branch(root: Path) -> str:
    head = read_text(root, ".git/HEAD") or ""
    match = re.match(r"ref: refs/heads/(.+)", head.strip())
    return match.group(1) if match else "main"


# --- Component detection ---------------------------------------------------------


@dataclass
class _Found:
    """One app directory and what it depends on. Commands run from `path`."""

    path: str
    kind: Kind
    framework: str
    build_command: str | None = None
    start_command: str | None = None
    port: int | None = None
    dependencies: set[str] = field(default_factory=set)


def _rel(directory: PurePosixPath) -> str:
    return "." if str(directory) in ("", ".") else str(directory)


def analyze_node(root: Path, directory: PurePosixPath) -> _Found | None:
    text = read_text(root, directory / "package.json")
    if text is None:
        return None
    try:
        manifest = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(manifest, dict) or "workspaces" in manifest:
        return None  # workspace roots hold no app of their own

    deps: set[str] = set()
    for key in ("dependencies", "devDependencies"):
        section = manifest.get(key)
        if isinstance(section, dict):
            deps.update(name.lower() for name in section)
    scripts = manifest.get("scripts") if isinstance(manifest.get("scripts"), dict) else {}

    path = _rel(directory)
    runner = _package_manager(root, directory)
    build = f"{runner} run build" if "build" in scripts else None

    backend = next((fw for dep, fw in NODE_BACKENDS if dep in deps), None)
    frontend = next((fw for dep, fw in NODE_FRONTENDS if dep in deps), None)
    if backend:
        start = f"{runner} start" if "start" in scripts else None
        return _Found(path, "backend", backend, build, start, 3000, deps)
    if frontend:
        # Next.js runs as a server (`next start`), so keep its start script too.
        start = f"{runner} start" if frontend == "next" and "start" in scripts else None
        return _Found(path, "frontend", frontend, build, start, None, deps)
    return None


def _package_manager(root: Path, directory: PurePosixPath) -> str:
    for lockfile, manager in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn")):
        if (root / directory / lockfile).is_file() or (root / lockfile).is_file():
            return manager
    return "npm"


def analyze_python(root: Path, directory: PurePosixPath) -> _Found | None:
    deps: set[str] = set()
    install = None
    requirements = read_text(root, directory / "requirements.txt")
    if requirements is not None:
        deps |= parse_requirements(requirements)
        install = "pip install -r requirements.txt"
    pyproject = read_text(root, directory / "pyproject.toml")
    if pyproject is not None:
        deps |= parse_pyproject(pyproject)
        install = install or "pip install ."
    if requirements is None and pyproject is None:
        return None

    framework = next((fw for fw in PYTHON_FRAMEWORKS if fw in deps), None)
    if framework is None:
        return None  # a library or script, not something to host

    path = _rel(directory)
    start = _python_start_command(root, directory, framework)
    return _Found(path, "backend", framework, install, start, DEFAULT_PORTS[framework], deps)


_ENTRY_CANDIDATES = ("main.py", "app.py", "server.py", "app/main.py", "src/main.py", "api/main.py")
_FRAMEWORK_MARKERS = {
    "fastapi": "FastAPI(",
    "flask": "Flask(",
    "streamlit": "import streamlit",
    "gradio": "import gradio",
}


def _python_start_command(root: Path, directory: PurePosixPath, framework: str) -> str | None:
    if framework == "django":
        for candidate in sorted(iter_files(root / directory, max_files=2_000)):
            if candidate.name == "wsgi.py" and len(candidate.parts) == 2:
                return f"gunicorn {candidate.parts[0]}.wsgi --bind 0.0.0.0:$PORT"
        return None

    marker = _FRAMEWORK_MARKERS[framework]
    others = sorted(
        entry.name
        for entry in _safe_listdir(root / directory)
        if entry.suffix == ".py" and entry.name not in _ENTRY_CANDIDATES
    )
    for candidate in (*_ENTRY_CANDIDATES, *others):
        text = read_text(root, directory / candidate)
        if text and marker in text:
            module = candidate.removesuffix(".py").replace("/", ".")
            if framework == "fastapi":
                return f"uvicorn {module}:app --host 0.0.0.0 --port $PORT"
            if framework == "flask":
                return f"gunicorn {module}:app --bind 0.0.0.0:$PORT"
            if framework == "streamlit":
                return f"streamlit run {candidate} --server.port $PORT --server.address 0.0.0.0"
            return f"python {candidate}"
    return None


def _safe_listdir(directory: Path) -> list[Path]:
    try:
        return [e for e in directory.iterdir() if e.is_file() and not e.is_symlink()]
    except OSError:
        return []


def detect_database(found: list[_Found], env_vars: list[str]) -> str | None:
    engines = Counter(
        DATABASE_DEPENDENCIES[dep]
        for item in found
        for dep in item.dependencies
        if dep in DATABASE_DEPENDENCIES
    )
    if engines:
        return engines.most_common(1)[0][0]
    if "DATABASE_URL" in env_vars:
        return "postgres"  # the common default for a bare DATABASE_URL
    return None


_ROOT_NAMES = {"frontend": "web", "backend": "api", "database": "db"}
_UI_FRAMEWORKS = frozenset({"streamlit", "gradio"})


def _component_name(path: str, kind: Kind, framework: str, taken: set[str]) -> str:
    if path != ".":
        base = PurePosixPath(path).name
    elif framework in _UI_FRAMEWORKS:
        base = "app"
    else:
        base = _ROOT_NAMES[kind]
    name, n = base, 2
    while name in taken:
        name, n = f"{base}-{n}", n + 1
    taken.add(name)
    return name


def analyze_repo(root: Path, repo_name: str) -> RepoProfile:
    """Build a RepoProfile from a checked-out repo. Raises ValueError if nothing is deployable."""
    files = list(iter_files(root))
    candidate_dirs = sorted(
        {f.parent for f in files if len(f.parts) <= MAX_COMPONENT_DEPTH + 1},
        key=lambda d: (len(d.parts), str(d)),
    )

    found: list[_Found] = []
    for directory in candidate_dirs:
        item = analyze_node(root, directory) or analyze_python(root, directory)
        if item:
            found.append(item)

    if not found and read_text(root, "Dockerfile") is not None:
        found.append(_Found(".", "backend", "docker", port=None))
    if not found and read_text(root, "index.html") is not None:
        found.append(_Found(".", "frontend", "static"))
    if not found:
        raise ValueError(
            "No deployable app found: no web framework in package.json, requirements.txt "
            "or pyproject.toml, and no Dockerfile or index.html at the root"
        )

    env_vars: list[str] = []
    env_dirs = dict.fromkeys([PurePosixPath("."), *(PurePosixPath(item.path) for item in found)])
    for directory in env_dirs:  # root first, then components in discovery order
        for filename in ENV_EXAMPLE_FILES:
            text = read_text(root, directory / filename)
            if text:
                env_vars.extend(parse_env_names(text))
    env_vars = list(dict.fromkeys(env_vars))

    taken: set[str] = set()
    components = [
        Component(
            name=_component_name(item.path, item.kind, item.framework, taken),
            kind=item.kind,
            path=item.path,
            framework=item.framework,
            build_command=item.build_command,
            start_command=item.start_command,
            port=item.port,
        )
        for item in found
    ]
    engine = detect_database(found, env_vars)
    if engine:
        components.append(
            Component(
                name=_component_name(".", "database", engine, taken),
                kind="database",
                path=".",
                framework=engine,
            )
        )

    return RepoProfile(
        name=repo_name,
        default_branch=default_branch(root),
        languages=detect_languages(files),
        frameworks=list(dict.fromkeys(item.framework for item in found)),
        components=components,
        env_vars=env_vars,
    )
