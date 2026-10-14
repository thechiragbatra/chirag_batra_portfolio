"""The sandbox deployment engine: build in containers, publish behind the router.

Semantics follow Vercel/Render:
- every deploy is an immutable directory with its own id and build log,
- a failed deploy never replaces the live one,
- a new server deploy must answer HTTP before traffic switches to it, and only
  then is the previous container stopped (no downtime),
- rollback re-points the router at an older deploy.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

from agents.base import LogFn
from agents.models import Component, LogLevel
from agents.sandbox import docker as dk
from agents.sandbox.recipes import APP_PORT, OUTPUT_DIRS, Recipe, recipe_for
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

INSTALL_TIMEOUT_S = 600.0
BUILD_TIMEOUT_S = 600.0
READY_TIMEOUT_S = 60.0
MAX_SOURCE_BYTES = 500 * 1024 * 1024
MAX_SITE_BYTES = 200 * 1024 * 1024
LOG_LINES_PER_STEP = 150  # streamed to the UI; the full log is always on disk
MAX_LINE = 300


class DeployError(RuntimeError):
    """The deploy failed; the previous live deploy (if any) is still serving."""


class Engine:
    def __init__(self, store: Store | None = None) -> None:
        self.store = store or Store()
        self._locks: dict[str, asyncio.Lock] = {}
        self._builds = asyncio.Semaphore(1)  # one build at a time on a laptop

    def _lock(self, app: str) -> asyncio.Lock:
        return self._locks.setdefault(app, asyncio.Lock())

    # --- deploy -----------------------------------------------------------------

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
        lockfile = (checkout / component.path / "package-lock.json").is_file()
        recipe = recipe_for(component, has_lockfile=lockfile)
        name = app_name(repo_name, component.name, single)
        await dk.ensure_docker()

        async with self._lock(name):
            record = self.store.load(name) or AppRecord(
                name=name, repo_url=repo_url, component=component.name, mode=recipe.mode
            )
            record.framework, record.mode = component.framework, recipe.mode
            deploy = Deployment(
                id=new_deploy_id(),
                created_at=datetime.now(UTC),
                status="building",
                mode=recipe.mode,
                component=component,
            )
            record.deployments.append(deploy)
            self.store.save(record)
            await log(f"Deploy {deploy.id} of {name} ({component.framework}, {recipe.mode})")

            try:
                async with self._builds:
                    await self._build_and_start(checkout, record, deploy, recipe, log)
            except BaseException as exc:
                deploy.status, deploy.error = "failed", str(exc) or type(exc).__name__
                self.store.save(record)
                if not isinstance(exc, DeployError | dk.SandboxError | ValueError):
                    raise
                if record.current:
                    await log(f"Previous deploy {record.current} is still live", LogLevel.warn)
                raise DeployError(str(exc)) from exc

            previous = record.current
            deploy.status, record.current = "ready", deploy.id
            self.store.save(record)
            await reload_router(self.store)
            if previous and record.mode == "server":
                await dk.remove_container(container_name(name, previous))
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
        log_path = self.store.log_path(record.name, deploy.id)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Static builds happen in a scratch copy; only the output is kept. Server
        # deploys keep the whole built tree, since the app runs from it.
        scratch = Path(tempfile.mkdtemp(prefix="deploysmith-build-"))
        source = scratch / "src" if recipe.mode == "static" else deploy_dir / "src"
        try:
            await log("Copying source into the sandbox (symlinks dropped)")
            await asyncio.to_thread(copy_tree_without_links, checkout, source, MAX_SOURCE_BYTES)
            workdir = source / recipe.workdir.removeprefix(dk.WORKDIR).lstrip("/")

            with log_path.open("a", encoding="utf-8") as build_log:
                if recipe.install:
                    await log(f"Install (network: registries only): {recipe.install}")
                    await self._step(
                        recipe, source, recipe.install, "bridge", build_log, log, INSTALL_TIMEOUT_S
                    )
                if recipe.build:
                    await log(f"Build (network: none): {recipe.build}")
                    await self._step(
                        recipe, source, recipe.build, "none", build_log, log, BUILD_TIMEOUT_S
                    )

            if recipe.mode == "static":
                output = find_output_dir(workdir)
                if output is None:
                    raise DeployError(
                        f"no index.html in {', '.join(OUTPUT_DIRS)} after the build; "
                        "set the build output directory"
                    )
                size = await asyncio.to_thread(
                    copy_tree_without_links, output, deploy_dir / "site", MAX_SITE_BYTES
                )
                rel = output.relative_to(source)
                await log(f"Published {rel}/ ({size // 1024} KB)")
            else:
                await self._start_server(record.name, deploy.id, recipe, source, log)
        except BaseException:
            shutil.rmtree(deploy_dir, ignore_errors=True)
            raise
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    async def _step(
        self,
        recipe: Recipe,
        source: Path,
        command: str,
        network: str,
        build_log: TextIO,
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
        )
        shown = 0

        async def on_line(line: str) -> None:
            nonlocal shown
            build_log.write(line + "\n")
            if line.strip() and shown < LOG_LINES_PER_STEP:
                shown += 1
                await log(f"│ {line[:MAX_LINE]}")

        code = await dk.run_streaming(dk.run_args(spec), on_line, timeout)
        if shown >= LOG_LINES_PER_STEP:
            await log("│ … output truncated; the full build log is on the dashboard")
        if code != 0:
            raise DeployError(f"`{command}` exited with code {code}")

    async def _start_server(
        self, app: str, deploy_id: str, recipe: Recipe, source: Path, log: LogFn
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
            env={**recipe.env, "PORT": str(APP_PORT)},
            limits=dk.RUN_LIMITS,
            name=name,
            detach=True,
            labels={dk.APP_LABEL: app},
        )
        await dk.ensure_network()
        await reload_router(self.store)  # the readiness check runs from the router
        await dk.remove_container(name)
        await log(f"Starting {recipe.start} (PORT={APP_PORT}, internal network only)")
        code, output = await dk.docker(*dk.run_args(spec)[1:])
        if code != 0:
            raise DeployError(f"container failed to start: {output[-500:]}")
        if not await self.wait_ready(name, log):
            _, tail = await dk.docker("logs", "--tail", "30", name)
            for line in tail.splitlines()[-30:]:
                await log(f"│ {line[:MAX_LINE]}", LogLevel.error)
            await dk.remove_container(name)
            raise DeployError(
                f"app did not answer HTTP on 0.0.0.0:$PORT ({APP_PORT}) "
                f"within {READY_TIMEOUT_S:.0f}s"
            )

    async def wait_ready(
        self, container: str, log: LogFn, timeout: float = READY_TIMEOUT_S
    ) -> bool:
        """Poll the container from the router until it returns any HTTP response."""
        deadline = asyncio.get_running_loop().time() + timeout
        url = f"http://{container}:{APP_PORT}/"
        while asyncio.get_running_loop().time() < deadline:
            if not await dk.container_running(container):
                await log("App container exited", LogLevel.error)
                return False
            _, output = await dk.docker(
                "exec",
                ROUTER_NAME,
                "wget",
                "-q",
                "-S",
                "-T",
                "3",
                "-O",
                "/dev/null",
                url,
                timeout=10,
            )
            if "HTTP/" in output:
                await log("App answered HTTP; switching traffic")
                return True
            await asyncio.sleep(1.5)
        return False

    # --- operations -------------------------------------------------------------

    async def rollback(self, app: str, deploy_id: str, log: LogFn) -> AppRecord:
        async with self._lock(app):
            record = self._require(app)
            deploy = record.deployment(deploy_id)
            if deploy is None or deploy.status != "ready":
                raise DeployError(f"{deploy_id} is not a successful deploy of {app}")
            if not self.store.deploy_dir(app, deploy_id).is_dir():
                raise DeployError(f"{deploy_id} has been pruned")
            if record.current == deploy_id:
                return record

            previous = record.current
            if record.mode == "server":
                source = self.store.deploy_dir(app, deploy_id) / "src"
                recipe = recipe_for(deploy.component)
                await self._start_server(app, deploy_id, recipe, source, log)
            record.current = deploy_id
            self.store.save(record)
            await reload_router(self.store)
            if previous and record.mode == "server":
                await dk.remove_container(container_name(app, previous))
            await log(f"{app} rolled back to {deploy_id}", LogLevel.success)
            return record

    async def stop(self, app: str, delete: bool = False) -> None:
        async with self._lock(app):
            record = self._require(app)
            for container in await dk.app_containers(app):
                await dk.remove_container(container)
            if delete:
                self.store.delete(app)
            else:
                record.current = None
                self.store.save(record)
            await reload_router(self.store)

    def _require(self, app: str) -> AppRecord:
        record = self.store.load(app)
        if record is None:
            raise DeployError(f"unknown app: {app}")
        return record


def find_output_dir(workdir: Path) -> Path | None:
    """The first conventional output dir with an index.html (one level deeper for Angular)."""
    for name in OUTPUT_DIRS:
        candidate = workdir / name
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        if (candidate / "index.html").is_file():
            return candidate
        for child in sorted(candidate.iterdir()):
            if child.is_dir() and not child.is_symlink():
                for nested in (child, child / "browser"):
                    if (nested / "index.html").is_file():
                        return nested
    if (workdir / "index.html").is_file():
        return workdir
    return None
