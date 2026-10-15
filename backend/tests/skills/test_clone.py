import asyncio
from pathlib import Path

import pytest

from agents.skills import clone as clone_module
from agents.skills.clone import CloneError, clone_command, clone_env, shallow_clone


def test_clone_command_is_hardened(tmp_path: Path) -> None:
    cmd = clone_command("https://github.com/acme/shop", tmp_path / "repo")
    joined = " ".join(cmd)
    assert cmd[0] == "git"
    for flag in (
        "protocol.allow=never",
        "protocol.https.allow=always",
        "core.hooksPath=/dev/null",
        "core.symlinks=false",
        "credential.helper=",
        "--depth 1",
        "--no-recurse-submodules",
        "--single-branch",
    ):
        assert flag in joined
    # The URL comes after "--" so it can never be parsed as an option.
    assert cmd[cmd.index("--") + 1] == "https://github.com/acme/shop"


@pytest.mark.parametrize(
    "url", ["file:///etc", "ext::sh -c id", "https://evil.com/a/b", "--upload-pack=x"]
)
def test_clone_command_rejects_non_github(url: str, tmp_path: Path) -> None:
    with pytest.raises(CloneError):
        clone_command(url, tmp_path)


def test_clone_env_ignores_host_git_config(tmp_path: Path) -> None:
    env = clone_env(tmp_path)
    assert env["GIT_CONFIG_NOSYSTEM"] == "1"
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["GIT_LFS_SKIP_SMUDGE"] == "1"
    assert env["HOME"] == str(tmp_path)
    assert not any(k.startswith(("GITHUB_", "AWS_")) for k in env)


class FakeProcess:
    def __init__(self, returncode: int, stderr: bytes = b"", hang: bool = False) -> None:
        self.returncode = returncode
        self._stderr = stderr
        self._hang = hang
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._hang:
            await asyncio.sleep(10)
        return b"", self._stderr

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return self.returncode


def fake_git(monkeypatch, process: FakeProcess, files: dict[str, bytes] | None = None):
    calls = {}

    async def create(*argv, **kwargs):
        calls["argv"], calls["kwargs"] = argv, kwargs
        dest = Path(argv[-1])
        for rel, data in (files or {}).items():
            (dest / rel).parent.mkdir(parents=True, exist_ok=True)
            (dest / rel).write_bytes(data)
        return process

    monkeypatch.setattr(clone_module.asyncio, "create_subprocess_exec", create)
    return calls


async def test_successful_clone_is_cleaned_up(monkeypatch) -> None:
    calls = fake_git(monkeypatch, FakeProcess(0), {"index.html": b"<p>"})
    async with shallow_clone("https://github.com/acme/shop") as checkout:
        assert (checkout / "index.html").read_bytes() == b"<p>"
        workdir = checkout.parent
    assert not workdir.exists()
    assert calls["kwargs"]["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
    assert "shell" not in calls["kwargs"]


async def test_missing_repo_reports_friendly_error(monkeypatch) -> None:
    fake_git(monkeypatch, FakeProcess(128, b"fatal: repository 'x' not found\n"))
    with pytest.raises(CloneError, match="not found or private"):
        async with shallow_clone("https://github.com/acme/nope"):
            pass


async def test_timeout_kills_git(monkeypatch) -> None:
    process = FakeProcess(0, hang=True)
    fake_git(monkeypatch, process)
    with pytest.raises(CloneError, match="timed out"):
        async with shallow_clone("https://github.com/acme/slow", timeout=0.05):
            pass
    assert process.killed


async def test_oversized_repo_is_rejected(monkeypatch) -> None:
    fake_git(monkeypatch, FakeProcess(0), {"big.bin": b"x" * 2048})
    with pytest.raises(CloneError, match="too large"):
        async with shallow_clone("https://github.com/acme/big", max_bytes=1024):
            pass


@pytest.mark.network
async def test_real_clone_of_public_repo() -> None:
    async with shallow_clone("https://github.com/octocat/Hello-World") as checkout:
        assert (checkout / "README").is_file()
        assert (checkout / ".git" / "shallow").is_file()  # depth-1 clone
