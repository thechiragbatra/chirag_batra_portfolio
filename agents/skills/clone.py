"""Shallow, hardened `git clone` of a public GitHub repo for static analysis.

Nothing from the target repo is ever executed. The clone:
- uses an argv list (no shell) and only the https transport (blocks ext::, file://, ssh),
- ignores the host's global/system git config (no LFS filters, credential helpers, aliases),
- skips submodules and LFS downloads, and disables hooks,
- checks symlinks out as plain files, so nothing in the tree can point outside it,
- is bounded by a timeout and a post-clone size cap, and always deleted afterwards.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

CLONE_TIMEOUT_S = 60.0
MAX_REPO_BYTES = 200 * 1024 * 1024


class CloneError(RuntimeError):
    """The repository could not be cloned safely."""


def clone_command(repo_url: str, dest: Path) -> list[str]:
    if not repo_url.startswith("https://github.com/"):
        raise CloneError("only https://github.com/ repositories can be cloned")
    return [
        "git",
        "-c", "protocol.allow=never",
        "-c", "protocol.https.allow=always",
        "-c", "credential.helper=",
        "-c", "core.hooksPath=/dev/null",
        "-c", "core.symlinks=false",
        "-c", "core.fsmonitor=false",
        "-c", "submodule.recurse=false",
        "clone",
        "--depth", "1",
        "--single-branch",
        "--no-tags",
        "--no-recurse-submodules",
        "--quiet",
        "--config", "core.symlinks=false",
        "--config", "core.hooksPath=/dev/null",
        "--",
        repo_url,
        str(dest),
    ]  # fmt: skip


def clone_env(home: Path) -> dict[str, str]:
    """A minimal environment: no inherited git settings, no prompts, no LFS smudge."""
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_LFS_SKIP_SMUDGE": "1",
        "GIT_ASKPASS": "",
        "LANG": "C",
    }


def tree_size(root: Path) -> int:
    total = 0
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            path = Path(dirpath, name)
            if not path.is_symlink():
                total += path.stat().st_size
    return total


@asynccontextmanager
async def shallow_clone(
    repo_url: str,
    *,
    timeout: float = CLONE_TIMEOUT_S,
    max_bytes: int = MAX_REPO_BYTES,
) -> AsyncIterator[Path]:
    """Clone into a fresh temp dir, yield the checkout, then delete everything."""
    workdir = Path(tempfile.mkdtemp(prefix="deploysmith-"))
    try:
        dest = workdir / "repo"
        process = await asyncio.create_subprocess_exec(
            *clone_command(repo_url, dest),
            cwd=workdir,
            env=clone_env(workdir),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise CloneError(f"clone timed out after {timeout:.0f}s") from None

        if process.returncode != 0:
            lines = stderr.decode(errors="replace").strip().splitlines()
            reason = lines[-1] if lines else f"git exited with {process.returncode}"
            if "not found" in reason.lower() or "could not read username" in reason.lower():
                reason = "repository not found or private"
            raise CloneError(reason)

        size = await asyncio.to_thread(tree_size, dest)
        if size > max_bytes:
            raise CloneError(f"repository is too large ({size // (1024 * 1024)} MB)")
        yield dest
    finally:
        await asyncio.to_thread(shutil.rmtree, workdir, True)
