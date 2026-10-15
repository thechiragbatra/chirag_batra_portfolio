"""The sandbox deployment engine: build in containers, publish behind the router.

Semantics follow Vercel/Render:
- every deploy is an immutable directory with its own id and build log,
- a failed deploy never replaces the live one,
- a new server deploy must answer HTTP before traffic switches to it, and only
  then is the previous container stopped (no downtime),
- rollback re-points the router at an older deploy.

One Engine per process (default_engine()) is shared by the pipeline and the dashboard
API, so its per-app locks serialize deploys, rollbacks and stops of the same app.
"""

from __future__ import annotations

import asyncio
import dataclasses
import logging
import os
import shutil
import tempfile
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from agents.base import LogFn
from agents.models import Component, LogLevel
from agents.sandbox import docker as dk
from agents.sandbox.recipes import (
    APP_PORT,
    GENERATED_REQUIREMENTS,
    OUTPUT_DIRS,
    PYTHON_SERVERS,
    Recipe,
    python_requirements,
    recipe_for,
)
from agents.sandbox.router import ROUTER_NAME, app_url, reload_router
from agents.sandbox.store import (
    AppRecord,
    Deployment,
    Store,
    app_name,
    container_name,
    copy_tree_without_links,
    new_deploy_id,
)
from agents.skills.clone import tree_size

logger = logging.getLogger(__name__)

INSTALL_TIMEOUT_S = 600.0
BUILD_TIMEOUT_S = 600.0
MAX_SOURCE_BYTES = 500 * 1024 * 1024
MAX_BUILD_TREE_BYTES = 3 * 1024 * 1024 * 1024  # source + dependencies after install/build
MAX_SITE_BYTES = 200 * 1024 * 1024
MAX_LOG_BYTES = 10 * 1024 * 1024  # per deploy, on disk
LOG_LINES_PER_STEP = 150  # streamed to the UI; the full log is on disk
MAX_LINE = 300
INTERRUPTED = "interrupted: the backend stopped or restarted during the deploy"


def ready_timeout() -> float:
    """Seconds a new server gets to answer HTTP (DEPLOYSMITH_READY_TIMEOUT, default 60)."""
    return float(os.getenv("DEPLOYSMITH_READY_TIMEOUT", "60"))


class DeployError(RuntimeError):
    """The deploy failed; the previous live deploy (if any) is still serving."""


class _BuildLog:
    """The on-disk build log: everything the steps print, capped at MAX_LOG_BYTES."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("a", encoding="utf-8")
        self._written = path.stat().st_size

    def write(self, line: str) -> None:
        if self._written > MAX_LOG_BYTES:
            return
        data = line + "\n"
        self._written += len(data.encode())
        self._file.write(data)
        if self._written > MAX_LOG_BYTES:
            self._file.write(f"[log truncated at {MAX_LOG_BYTES // (1024 * 1024)} MB]\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()


class Engine:
    def __init__(self, store: Store | None = None) -> None:
        self.store = store or Store()
        self._locks: dict[str, asyncio.Lock] = {}
        self._builds = asyncio.Semaphore(1)  # one build at a time on a laptop

    def _lock(self, app: str) -> asyncio.Lock:
        return self._locks.setdefault(app, asyncio.Lock())

    def _busy(self, app: str) -> None:
        if self._lock(app).locked():
            raise DeployError(f"a deploy or rollback of {app} is in progress; try again shortly")

    # --- deploy -----------------------------------------------------------------

    def _resolve_name(self, repo_url: str, repo_name: str, component: str, single: bool) -> str:
        """The short name, unless a different repo already owns it (then owner-repo)."""
        name = app_name(repo_name, component, single)
        try:
            existing = self.store.load(name)
        except ValueError:
            existing = None
        if existing is not None and existing.repo_url != repo_url:
            return app_name(repo_name, component, single, with_owner=True)
        return name

    async def deploy(
        self,
        checkout: Path,
        repo_url: str,
        repo_name: str,
        component: Component,
        single: bool,
        log: LogFn,
    ) -> tuple[str, str]:
        """Build and publish one component. Returns (app name, URL)."""
        recipe = recipe_for(component, has_lockfile=_has_lockfile(checkout, component.path))
        name = self._resolve_name(repo_url, repo_name, component.name, single)
        await dk.ensure_docker()
        # Fail fast on router problems (port taken, Docker issue) before minutes of building.
        await reload_router(self.store)

        async with self._lock(name):
            record = self.store.load(name) or AppRecord(
                name=name, repo_url=repo_url, component=component.name, mode=recipe.mode
            )
            deploy = Deployment(
                id=new_deploy_id(),
                created_at=datetime.now(UTC),
                status="building",
                mode=recipe.mode,
                component=component,
                image=recipe.image,
            )
            record.deployments.append(deploy)
            self.store.save(record)
            await log(f"Deploy {deploy.id} of {name} ({component.framework}, {recipe.mode})")

            try:
                async with self._builds:
                    await self._build_and_start(checkout, record, deploy, recipe, log)
            except BaseException as exc:
                cancelled = isinstance(exc, asyncio.CancelledError)
                deploy.status = "failed"
                deploy.error = INTERRUPTED if cancelled else str(exc) or type(exc).__name__
                self.store.save(record)
                if not isinstance(exc, DeployError | dk.SandboxError | ValueError):
                    raise
                if record.current:
                    await log(f"Previous deploy {record.current} is still live", LogLevel.warn)
                raise DeployError(str(exc)) from exc

            previous = record.deployment(record.current) if record.current else None
            deploy.status, record.current = "ready", deploy.id
            record.framework, record.mode = component.framework, recipe.mode
            self.store.save(record)
            try:
                await reload_router(self.store)
            except dk.SandboxError as exc:
                # The build is fine but nothing can serve it: do not claim it is live.
                record.current = previous.id if previous else None
                deploy.status, deploy.error = "failed", f"router: {exc}"
                self.store.save(record)
                await dk.remove_container(container_name(name, deploy.id))
                raise DeployError(
                    f"{exc}. If the router port is taken, set DEPLOYSMITH_ROUTER_PORT"
                ) from exc
            if previous and previous.mode == "server":
                await dk.remove_container(container_name(name, previous.id))
            for removed in self.store.prune(record):
                await dk.remove_container(container_name(name, removed))
            self.store.save(record)

        url = app_url(name)
        await log(f"{name} is live at {url}", LogLevel.success)
        return name, url

    async def _build_and_start(
        self, checkout: Path, record: AppRecord, deploy: Deployment, recipe: Recipe, log: LogFn
    ) -> None:
        deploy_dir = self.store.deploy_dir(record.name, deploy.id)
        build_log = _BuildLog(self.store.log_path(record.name, deploy.id))

        # Static builds happen in a scratch copy; only the output is kept. Server
        # deploys keep the whole built tree, since the app runs from it.
        scratch = Path(tempfile.mkdtemp(prefix="deploysmith-build-"))
        source = scratch / "src" if recipe.mode == "static" else deploy_dir / "src"
        try:
            await log("Copying source into the sandbox (symlinks dropped)")
            await asyncio.to_thread(copy_tree_without_links, checkout, source, MAX_SOURCE_BYTES)
            workdir = source / recipe.workdir.removeprefix(dk.WORKDIR).lstrip("/")
            _write_generated_requirements(deploy.component, workdir)
            existing_outputs = _output_snapshot(workdir)

            steps = (
                ("install", recipe.install, "bridge", INSTALL_TIMEOUT_S,
                 "Install (outbound network allowed, for package registries)"),
                ("build", recipe.build, "none", BUILD_TIMEOUT_S, "Build (no network)"),
            )  # fmt: skip
            for step, command, network, timeout, label in steps:
                if not command:
                    continue
                await log(f"{label}: {command}")
                name = f"{container_name(record.name, deploy.id)}-{step}"
                await self._step(
                    recipe, source, command, network, name, record.name, build_log, log, timeout
                )
                size = await asyncio.to_thread(tree_size, source)
                if size > MAX_BUILD_TREE_BYTES:
                    raise DeployError(
                        f"the {step} step grew the tree to {size // (1024 * 1024)} MB "
                        f"(limit {MAX_BUILD_TREE_BYTES // (1024 * 1024)} MB)"
                    )

            if recipe.mode == "static":
                output = find_output_dir(workdir, built=bool(recipe.build), before=existing_outputs)
                if output is None:
                    raise DeployError(
                        "no new index.html in dist/, build/ or out/ after the build; "
                        "set the build output directory"
                    )
                size = await asyncio.to_thread(
                    copy_tree_without_links, output, deploy_dir / "site", MAX_SITE_BYTES, source
                )
                rel = output.relative_to(source)
                await log(f"Published {rel}/ ({size // 1024} KB)")
            else:
                await self._start_server(record.name, deploy.id, recipe, source, log, build_log)
        except BaseException:
            shutil.rmtree(deploy_dir, ignore_errors=True)
            raise
        finally:
            build_log.close()
            shutil.rmtree(scratch, ignore_errors=True)

    async def _step(
        self,
        recipe: Recipe,
        source: Path,
        command: str,
        network: str,
        name: str,
        app: str,
        build_log: _BuildLog,
        log: LogFn,
        timeout: float,
    ) -> None:
        spec = dk.Container(
            image=recipe.image,
            command=command,
            source=source,
            workdir=recipe.workdir,
            network=network,
            env=recipe.env,
            name=name,
            labels={dk.APP_LABEL: app},
        )
        shown = 0

        async def on_line(line: str) -> None:
            nonlocal shown
            build_log.write(line)
            if line.strip() and shown < LOG_LINES_PER_STEP:
                shown += 1
                await log(f"│ {line[:MAX_LINE]}")

        try:
            code = await dk.run_streaming(dk.run_args(spec), on_line, timeout)
        finally:
            # Killing the docker CLI (timeout, error, cancellation) does not stop the
            # container; remove it by name so nothing keeps running unobserved.
            await asyncio.shield(dk.remove_container(name))
        if shown >= LOG_LINES_PER_STEP:
            await log("│ … output truncated; the full build log is on the Apps page")
        if code != 0:
            raise DeployError(f"`{command}` exited with code {code}")

    async def _start_server(
        self,
        app: str,
        deploy_id: str,
        recipe: Recipe,
        source: Path,
        log: LogFn,
        build_log: _BuildLog | None = None,
    ) -> None:
        if not recipe.start:
            raise DeployError("no start command")
        name = container_name(app, deploy_id)
        spec = dk.Container(
            image=recipe.image,
            command=recipe.start,
            source=source,
            workdir=recipe.workdir,
            network=dk.APPS_NETWORK,
            env={**recipe.env, **recipe.run_env, "PORT": str(APP_PORT)},
            limits=dk.RUN_LIMITS,
            name=name,
            detach=True,
            labels={dk.APP_LABEL: app},
        )

        def record(line: str) -> None:
            if build_log is not None:
                build_log.write(line)

        await dk.ensure_network()
        await reload_router(self.store)  # the readiness check runs from the router
        await dk.remove_container(name)
        await log(f"Starting {recipe.start} (PORT={APP_PORT}, internal network only)")
        record(f"$ {recipe.start}")
        code, output = await dk.docker(*dk.run_args(spec)[1:])
        if code != 0:
            record(output)
            raise DeployError(f"container failed to start: {output[-500:]}")
        timeout = ready_timeout()
        if not await self.wait_ready(name, log, timeout):
            _, tail = await dk.docker("logs", "--tail", "30", name)
            record("--- app output (last 30 lines) ---")
            for line in tail.splitlines()[-30:]:
                record(line)
                await log(f"│ {line[:MAX_LINE]}", LogLevel.error)
            await dk.remove_container(name)
            raise DeployError(
                f"app did not answer HTTP on 0.0.0.0:$PORT ({APP_PORT}) within {timeout:.0f}s "
                "(raise DEPLOYSMITH_READY_TIMEOUT for slow starters)"
            )
        record("app answered HTTP")

    async def wait_ready(self, container: str, log: LogFn, timeout: float | None = None) -> bool:
        """Poll the container from the router until it returns any HTTP response."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + (timeout if timeout is not None else ready_timeout())
        url = f"http://{container}:{APP_PORT}/"
        while loop.time() < deadline:
            if not await dk.container_running(container):
                await log("App container exited", LogLevel.error)
                return False
            _, output = await dk.docker(
                "exec", ROUTER_NAME, "wget", "-q", "-S", "-T", "3", "-O", "/dev/null", url,
                timeout=10,
            )  # fmt: skip
            if "HTTP/" in output:
                await log("App answered HTTP; switching traffic")
                return True
            await asyncio.sleep(1.5)
        return False

    # --- operations -------------------------------------------------------------

    async def rollback(self, app: str, deploy_id: str, log: LogFn) -> AppRecord:
        self._busy(app)
        await dk.ensure_docker()  # before any change, so Docker being down modifies nothing
        async with self._lock(app):
            record = self._require(app)
            deploy = record.deployment(deploy_id)
            if deploy is None or deploy.status != "ready":
                raise DeployError(f"{deploy_id} is not a successful deploy of {app}")
            if not self.store.deploy_dir(app, deploy_id).is_dir():
                raise DeployError(f"{deploy_id} has been pruned")
            if record.current == deploy_id:
                return record

            previous = record.deployment(record.current) if record.current else None
            if deploy.mode == "server":
                source = self.store.deploy_dir(app, deploy_id) / "src"
                await self._start_server(app, deploy_id, _recipe_of(deploy), source, log)
            record.current = deploy_id
            record.mode, record.framework = deploy.mode, deploy.component.framework
            self.store.save(record)
            await reload_router(self.store)
            if previous and previous.mode == "server":
                await dk.remove_container(container_name(app, previous.id))
            await log(f"{app} rolled back to {deploy_id}", LogLevel.success)
            return record

    async def stop(self, app: str, delete: bool = False) -> None:
        self._busy(app)
        await dk.ensure_docker()
        async with self._lock(app):
            record = self._require(app)
            # Containers first: a record is only dropped once nothing of it is running.
            for container in await dk.app_containers(app):
                await dk.remove_container(container)
            if delete:
                self.store.delete(app)
            else:
                record.current = None
                self.store.save(record)
            await reload_router(self.store)

    async def reconcile(self) -> list[str]:
        """Repair state after a backend or Docker restart. Returns what was done.

        Deploys left 'building' by a dead process are marked failed, and the live server
        container of every app is started (or recreated from its deploy) if it is down.
        """
        actions: list[str] = []
        records = self.store.list()
        for record in records:
            changed = False
            for deploy in record.deployments:
                if deploy.status == "building" and not self._lock(record.name).locked():
                    deploy.status, deploy.error = "failed", INTERRUPTED
                    shutil.rmtree(self.store.deploy_dir(record.name, deploy.id), ignore_errors=True)
                    actions.append(f"{record.name}: marked {deploy.id} failed (interrupted)")
                    changed = True
            if changed:
                self.store.save(record)
        try:
            await dk.ensure_docker()
        except dk.SandboxError:
            return actions  # nothing to restart without Docker; records are still fixed
        for record in records:
            live = record.deployment(record.current) if record.current else None
            if live is None or live.mode != "server" or self._lock(record.name).locked():
                continue
            name = container_name(record.name, live.id)
            if await dk.container_running(name):
                continue
            if await dk.container_exists(name) and await dk.start_container(name):
                actions.append(f"{record.name}: restarted {name}")
                continue
            source = self.store.deploy_dir(record.name, live.id) / "src"
            if not source.is_dir():
                continue
            try:
                async with self._lock(record.name):
                    await self._start_server(
                        record.name, live.id, _recipe_of(live), source, _logger_for(record.name)
                    )
                actions.append(f"{record.name}: recreated {name}")
            except (DeployError, dk.SandboxError, ValueError) as exc:
                actions.append(f"{record.name}: could not restart {name}: {exc}")
        if any(r.current for r in records):
            await reload_router(self.store)
        return actions

    def _require(self, app: str) -> AppRecord:
        record = self.store.load(app)
        if record is None:
            raise DeployError(f"unknown app: {app}")
        return record


@lru_cache(maxsize=1)
def default_engine() -> Engine:
    """The process-wide engine shared by the pipeline and the dashboard API."""
    return Engine()


def _logger_for(app: str) -> LogFn:
    async def log(message: str, level: LogLevel = LogLevel.info) -> None:
        logger.info("reconcile %s: %s", app, message)

    return log


def _recipe_of(deploy: Deployment) -> Recipe:
    """The recipe a deploy was built with, on the image it was built with."""
    recipe = recipe_for(deploy.component)
    return dataclasses.replace(recipe, image=deploy.image) if deploy.image else recipe


def _has_lockfile(checkout: Path, path: str) -> bool:
    names = ("package-lock.json", "pnpm-lock.yaml", "yarn.lock")
    return any((checkout / path / n).is_file() or (checkout / n).is_file() for n in names)


def _write_generated_requirements(component: Component, workdir: Path) -> None:
    """For a Python app that declares dependencies only in pyproject.toml without a build
    backend, write them to a requirements file the recipe installs from."""
    if component.framework not in PYTHON_SERVERS or (workdir / "requirements.txt").is_file():
        return
    pyproject = workdir / "pyproject.toml"
    if pyproject.is_symlink() or not pyproject.is_file():
        return
    lines = python_requirements(pyproject.read_text(encoding="utf-8", errors="replace"))
    if lines:
        (workdir / GENERATED_REQUIREMENTS).write_text("\n".join(lines) + "\n")


def _output_snapshot(workdir: Path) -> dict[str, float]:
    """mtimes of output candidates that exist before the build (committed to the repo)."""
    snapshot: dict[str, float] = {}
    for name in OUTPUT_DIRS:
        found = _index_dir(workdir / name) if (workdir / name).is_dir() else None
        if found is not None and not found.is_symlink():
            snapshot[name] = (found / "index.html").stat().st_mtime
    return snapshot


def find_output_dir(
    workdir: Path, built: bool = False, before: dict[str, float] | None = None
) -> Path | None:
    """The build's output: the first conventional dir with an index.html (one level deeper
    for Angular).

    For a built app only output the build produced counts: public/ and the app root are
    inputs (Vite/CRA source), and a dist/ committed to the repo is ignored unless the
    build rewrote it. For a plain static site (no build) the root itself is the site.
    """
    before = before or {}
    candidates = OUTPUT_DIRS if not built else tuple(n for n in OUTPUT_DIRS if n != "public")
    for name in candidates:
        candidate = workdir / name
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        found = _index_dir(candidate)
        if found is None:
            continue
        if built and name in before and (found / "index.html").stat().st_mtime <= before[name]:
            continue  # committed to the repo and untouched by the build
        return found
    if not built and (workdir / "index.html").is_file():
        return workdir
    return None


def _index_dir(candidate: Path) -> Path | None:
    if (candidate / "index.html").is_file():
        return candidate
    for child in sorted(candidate.iterdir()):
        if child.is_dir() and not child.is_symlink():
            for nested in (child, child / "browser"):
                # The build ran repo code that could leave `browser` as a symlink to a
                # host directory; never return a link.
                if nested.is_symlink():
                    continue
                if (nested / "index.html").is_file():
                    return nested
    return None
