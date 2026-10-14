"""Hardened `docker` invocations. The only place repo code is allowed to execute.

Every container the engine starts gets the same baseline (see CLAUDE.md):
non-root user, all capabilities dropped, no-new-privileges, read-only root
filesystem with a small /tmp, CPU/memory/PID limits, an init process, and only
one bind mount: the per-deploy copy of the repo. Build steps run with no network;
installs get the default bridge (package registries); running apps sit on an
internal network that only the router can reach.

Commands are argv lists (no host shell). Shell syntax inside the container is fine:
it can only affect the container.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

NODE_IMAGE = "node:22-alpine"
PYTHON_IMAGE = "python:3.12-slim"
ROUTER_IMAGE = "nginx:1.27-alpine"

APPS_NETWORK = "deploysmith-apps"
LABEL = "dev.deploysmith.engine=1"
APP_LABEL = "dev.deploysmith.app"
SANDBOX_UID = "1000:1000"
WORKDIR = "/app"

LineFn = Callable[[str], Awaitable[None]]
_NAME = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,127}$")


class SandboxError(RuntimeError):
    """A docker step failed, timed out, or Docker is unavailable."""


@dataclass(frozen=True)
class Limits:
    memory: str = "2g"
    cpus: str = "2"
    pids: int = 512
    tmp_size: str = "1g"


BUILD_LIMITS = Limits()
RUN_LIMITS = Limits(memory="512m", cpus="1", pids=256, tmp_size="256m")


@dataclass(frozen=True)
class Container:
    image: str
    command: str
    source: Path
    workdir: str = WORKDIR
    network: str = "none"
    env: dict[str, str] = field(default_factory=dict)
    limits: Limits = BUILD_LIMITS
    name: str | None = None
    detach: bool = False
    labels: dict[str, str] = field(default_factory=dict)


def run_args(spec: Container) -> list[str]:
    """`docker run` argv for a sandboxed step or app. Pure, so the flags are testable."""
    if not spec.source.is_absolute():
        raise SandboxError("source must be an absolute path")
    if spec.name is not None and not _NAME.match(spec.name):
        raise SandboxError(f"invalid container name: {spec.name!r}")
    if not (spec.workdir == WORKDIR or spec.workdir.startswith(WORKDIR + "/")):
        raise SandboxError("workdir must be inside the mounted source")
    if ".." in spec.workdir.split("/"):
        raise SandboxError("workdir must not contain '..'")

    args = ["docker", "run"]
    args += ["--detach", "--restart", "on-failure:3"] if spec.detach else ["--rm"]
    if spec.name:
        args += ["--name", spec.name]
    args += [
        "--label", LABEL,
        *[f"--label={key}={value}" for key, value in sorted(spec.labels.items())],
        "--user", SANDBOX_UID,
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--read-only",
        "--tmpfs", f"/tmp:rw,exec,nosuid,nodev,size={spec.limits.tmp_size}",
        "--memory", spec.limits.memory,
        "--memory-swap", spec.limits.memory,
        "--cpus", spec.limits.cpus,
        "--pids-limit", str(spec.limits.pids),
        "--init",
        "--network", spec.network,
        "--volume", f"{spec.source}:{WORKDIR}:rw",
        "--workdir", spec.workdir,
        "--env", "HOME=/tmp",
        "--env", "CI=1",
    ]  # fmt: skip
    for key, value in sorted(spec.env.items()):
        args += ["--env", f"{key}={value}"]
    args += [spec.image, "sh", "-c", spec.command]
    return args


async def _discard(_: str) -> None:
    return None


async def run_streaming(
    argv: Sequence[str], on_line: LineFn = _discard, timeout: float = 600.0
) -> int:
    """Run a docker command, feeding each output line to `on_line`. Returns the exit code."""
    try:
        process = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        raise SandboxError("docker is not installed or not on PATH") from None
    assert process.stdout is not None

    async def pump() -> None:
        assert process.stdout is not None
        while line := await process.stdout.readline():
            await on_line(line.decode(errors="replace").rstrip())

    try:
        await asyncio.wait_for(asyncio.gather(pump(), process.wait()), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise SandboxError(f"step timed out after {timeout:.0f}s") from None
    return process.returncode if process.returncode is not None else -1


async def docker(*args: str, timeout: float = 60.0) -> tuple[int, str]:
    """A short docker CLI call (inspect, rm, network...). Returns (exit code, output)."""
    lines: list[str] = []

    async def keep(line: str) -> None:
        lines.append(line)

    code = await run_streaming(["docker", *args], keep, timeout)
    return code, "\n".join(lines)


async def ensure_docker() -> None:
    code, output = await docker("version", "--format", "{{.Server.Version}}", timeout=15)
    if code != 0:
        raise SandboxError("Docker is not running; start Docker Desktop and retry")


async def ensure_network(name: str = APPS_NETWORK) -> None:
    """An internal bridge: apps on it reach each other and the router, never the internet."""
    code, _ = await docker("network", "inspect", name)
    if code == 0:
        return
    code, output = await docker("network", "create", "--internal", "--label", LABEL, name)
    if code != 0 and "already exists" not in output:
        raise SandboxError(f"could not create network {name}: {output}")


async def remove_container(name: str) -> None:
    await docker("rm", "--force", name)


async def app_containers(app: str) -> list[str]:
    """Names of every container (running or not) the engine started for `app`."""
    code, output = await docker(
        "ps", "--all", "--filter", f"label={APP_LABEL}={app}", "--format", "{{.Names}}"
    )
    return [line for line in output.splitlines() if line.strip()] if code == 0 else []


async def container_running(name: str) -> bool:
    code, output = await docker("inspect", "--format", "{{.State.Running}}", name)
    return code == 0 and output.strip() == "true"
