"""Sandbox engine: hardening flags, recipes, store, router config, and deploy
semantics with a fake docker. The real-container test is marked `docker`."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import pytest

from agents.models import Component, LogLevel
from agents.sandbox import docker as dk
from agents.sandbox import engine as engine_mod
from agents.sandbox.engine import DeployError, Engine, find_output_dir
from agents.sandbox.recipes import UnsupportedComponent, recipe_for
from agents.sandbox.router import app_url, sites_config
from agents.sandbox.store import (
    AppRecord,
    Deployment,
    Store,
    app_name,
    copy_tree_without_links,
    new_deploy_id,
)


async def quiet(message: str, level: LogLevel = LogLevel.info) -> None:
    return None


def component(**overrides: Any) -> Component:
    base: dict[str, Any] = dict(
        name="web", kind="frontend", path=".", framework="vite", build_command="npm run build"
    )
    return Component(**{**base, **overrides})


# --- docker flags -------------------------------------------------------------------


def test_run_args_apply_full_hardening(tmp_path: Path) -> None:
    args = dk.run_args(dk.Container(image="node:22-alpine", command="npm ci", source=tmp_path))
    joined = " ".join(args)
    for flag in (
        "--rm",
        "--user 1000:1000",
        "--cap-drop ALL",
        "--security-opt no-new-privileges",
        "--read-only",
        "--network none",
        "--pids-limit 512",
        "--memory 2g",
        "--init",
    ):
        assert flag in joined, flag
    assert args[-4:] == ["node:22-alpine", "sh", "-c", "npm ci"]
    # The per-deploy copy is the only mount; never the docker socket or a host dir.
    mounts = [args[i + 1] for i, a in enumerate(args) if a == "--volume"]
    assert mounts == [f"{tmp_path}:/app:rw"]
    assert "--privileged" not in args and "/var/run/docker.sock" not in joined


def test_run_args_for_detached_app(tmp_path: Path) -> None:
    spec = dk.Container(
        image="python:3.12-slim",
        command="uvicorn main:app",
        source=tmp_path,
        network=dk.APPS_NETWORK,
        limits=dk.RUN_LIMITS,
        name="ds-shop-d1",
        detach=True,
        labels={dk.APP_LABEL: "shop"},
    )
    args = dk.run_args(spec)
    assert "--detach" in args and "--rm" not in args
    assert f"--label={dk.APP_LABEL}=shop" in args
    assert args[args.index("--network") + 1] == dk.APPS_NETWORK


@pytest.mark.parametrize(
    "overrides, error",
    [
        ({"source": Path("relative")}, "absolute"),
        ({"workdir": "/etc"}, "inside"),
        ({"workdir": "/app/../etc"}, ".."),
        ({"name": "Bad Name;rm"}, "invalid container name"),
    ],
)
def test_run_args_reject_unsafe_specs(
    tmp_path: Path, overrides: dict[str, Any], error: str
) -> None:
    spec = dk.Container(**{"image": "x", "command": "true", "source": tmp_path, **overrides})
    with pytest.raises(dk.SandboxError, match=error):
        dk.run_args(spec)


# --- recipes ------------------------------------------------------------------------


def test_vite_recipe_is_static_with_npm_ci_when_locked() -> None:
    recipe = recipe_for(component(path="frontend"), has_lockfile=True)
    assert recipe.mode == "static" and recipe.workdir == "/app/frontend"
    assert recipe.install == "npm ci --no-audit --no-fund" and recipe.build == "npm run build"


def test_pnpm_goes_through_corepack() -> None:
    recipe = recipe_for(component(build_command="pnpm run build"))
    assert recipe.install == "corepack pnpm install --frozen-lockfile"
    assert recipe.build == "corepack pnpm run build"


def test_express_recipe_runs_start_script() -> None:
    recipe = recipe_for(
        component(
            kind="backend", framework="express", start_command="npm start", build_command=None
        )
    )
    assert recipe.mode == "server" and recipe.start == "npm start" and recipe.build is None


def test_fastapi_recipe_uses_venv_and_installs_uvicorn() -> None:
    recipe = recipe_for(
        component(
            kind="backend",
            framework="fastapi",
            path="api",
            start_command="uvicorn main:app --host 0.0.0.0 --port $PORT",
        )
    )
    assert recipe.image == dk.PYTHON_IMAGE and "pip install uvicorn" in (recipe.install or "")
    assert recipe.env["PATH"].startswith("/app/api/.venv/bin")


@pytest.mark.parametrize(
    "overrides, reason",
    [
        ({"kind": "database", "framework": "postgres"}, "databases"),
        ({"framework": "nuxt"}, "no sandbox recipe"),
        ({"build_command": None}, "no build script"),
        ({"kind": "backend", "framework": "flask", "start_command": None}, "no entry point"),
        ({"path": "../etc"}, "unsafe component path"),
    ],
)
def test_unsupported_components(overrides: dict[str, Any], reason: str) -> None:
    with pytest.raises(UnsupportedComponent, match=reason):
        recipe_for(component(**overrides))


# --- store --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "repo, comp, single, expected",
    [
        ("acme/My_Shop", "web", True, "my-shop"),
        ("acme/shop", "api", False, "shop-api"),
        ("acme/---", "web", True, "app"),
        ("acme/" + "x" * 80, "web", True, "x" * 40),
    ],
)
def test_app_name_is_dns_safe(repo: str, comp: str, single: bool, expected: str) -> None:
    assert app_name(repo, comp, single) == expected


def test_store_rejects_path_traversal(tmp_path: Path) -> None:
    store = Store(tmp_path)
    with pytest.raises(ValueError):
        store.app_dir("../escape")
    with pytest.raises(ValueError):
        store.deploy_dir("shop", "../../etc")


def _record(n: int, current: int | None) -> AppRecord:
    deploys = [
        Deployment(
            id=f"d2026010100000{i}abcd",
            created_at="2026-01-01T00:00:00Z",
            status="ready",
            mode="static",
            component=component(),
        )
        for i in range(n)
    ]
    return AppRecord(
        name="shop",
        repo_url="u",
        component="web",
        mode="static",
        current=deploys[current].id if current is not None else None,
        deployments=deploys,
    )


def test_prune_keeps_newest_and_current(tmp_path: Path) -> None:
    store = Store(tmp_path)
    record = _record(6, current=0)
    for d in record.deployments:
        store.deploy_dir("shop", d.id).mkdir(parents=True)
    removed = store.prune(record, keep=3)
    kept = {d.id for d in record.deployments}
    assert record.current in kept and len(kept) == 4 and len(removed) == 2
    assert all(not store.deploy_dir("shop", r).exists() for r in removed)


def test_copy_drops_symlinks(tmp_path: Path) -> None:
    src = tmp_path / "src"
    (src / "assets").mkdir(parents=True)
    (src / "index.html").write_text("hi")
    (src / "assets" / "a.js").write_text("x")
    secret = tmp_path / "host-secret"
    secret.write_text("TOKEN")
    os.symlink(secret, src / "leak.txt")
    os.symlink(tmp_path, src / "linkdir")
    copy_tree_without_links(src, tmp_path / "out", max_bytes=10_000)
    copied = sorted(
        p.relative_to(tmp_path / "out").as_posix() for p in (tmp_path / "out").rglob("*")
    )
    assert copied == ["assets", "assets/a.js", "index.html"]


def test_copy_enforces_size_cap(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "big").write_bytes(b"x" * 2000)
    with pytest.raises(ValueError, match="exceeds"):
        copy_tree_without_links(tmp_path / "src", tmp_path / "out", max_bytes=1000)


@pytest.mark.parametrize(
    "layout, expected",
    [
        (["dist/index.html"], "dist"),
        (["build/index.html", "dist/other.txt"], "build"),
        (["dist/shop/browser/index.html"], "dist/shop/browser"),
        (["index.html"], "."),
        (["dist/app.js"], None),
    ],
)
def test_find_output_dir(tmp_path: Path, layout: list[str], expected: str | None) -> None:
    for rel in layout:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x")
    found = find_output_dir(tmp_path)
    assert (found.relative_to(tmp_path).as_posix() if found else None) == expected


# --- router -------------------------------------------------------------------------


def test_sites_config_routes_static_and_server_apps() -> None:
    static = _record(1, current=0)
    server = AppRecord(
        name="shop-api", repo_url="u", component="api", mode="server", current="d20260101000000beef"
    )
    idle = AppRecord(name="idle", repo_url="u", component="web", mode="static")
    config = sites_config([server, static, idle])
    assert "server_name shop.localhost;" in config
    assert f"root /srv/apps/shop/deploys/{static.current}/site;" in config
    assert "set $upstream http://ds-shop-api-d20260101000000beef:8000;" in config
    assert "idle.localhost" not in config and "default_server" in config


def test_app_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYSMITH_ROUTER_PORT", "9000")
    assert app_url("shop") == "http://shop.localhost:9000"


# --- engine semantics with a fake docker --------------------------------------------


class FakeDocker:
    """Simulates container steps; `fail_on` makes the matching command exit 1."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, fail_on: str | None = None) -> None:
        self.commands: list[str] = []
        self.fail_on = fail_on
        self.routes = 0

        async def run_streaming(argv: list[str], on_line: Any, timeout: float) -> int:
            command = argv[-1]
            self.commands.append(command)
            await on_line(f"running {command}")
            if command == "npm run build":
                workdir = Path(argv[argv.index("--volume") + 1].split(":")[0])
                (workdir / "dist").mkdir()
                (workdir / "dist" / "index.html").write_text(f"build {len(self.commands)}")
            return 1 if self.fail_on and self.fail_on in command else 0

        async def nothing(*_: Any, **__: Any) -> None:
            return None

        async def reload(_: Store) -> None:
            self.routes += 1

        monkeypatch.setattr(dk, "run_streaming", run_streaming)
        monkeypatch.setattr(dk, "ensure_docker", nothing)
        monkeypatch.setattr(dk, "remove_container", nothing)
        monkeypatch.setattr(engine_mod, "reload_router", reload)


def checkout(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "package.json").write_text("{}")
    (repo / "package-lock.json").write_text("{}")
    return repo


async def test_static_deploy_publishes_output_and_switches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeDocker(monkeypatch)
    engine = Engine(Store(tmp_path / "engine"))
    name, url = await engine.deploy(checkout(tmp_path), "u", "acme/shop", component(), True, quiet)
    assert (name, url) == ("shop", "http://shop.localhost:8080")
    assert fake.commands == ["npm ci --no-audit --no-fund", "npm run build"]
    record = engine.store.load("shop")
    assert record and record.current and record.deployments[0].status == "ready"
    site = engine.store.deploy_dir("shop", record.current) / "site" / "index.html"
    assert site.read_text().startswith("build") and fake.routes == 1
    assert engine.store.log_path("shop", record.current).read_text().count("running") == 2


async def test_failed_deploy_keeps_previous_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    FakeDocker(monkeypatch)
    engine = Engine(Store(tmp_path / "engine"))
    repo = checkout(tmp_path)
    await engine.deploy(repo, "u", "acme/shop", component(), True, quiet)
    live = engine.store.load("shop").current  # type: ignore[union-attr]

    FakeDocker(monkeypatch, fail_on="npm run build")
    with pytest.raises(DeployError, match="exited with code 1"):
        await engine.deploy(repo, "u", "acme/shop", component(), True, quiet)
    record = engine.store.load("shop")
    assert record and record.current == live
    assert [d.status for d in record.deployments] == ["ready", "failed"]
    failed = record.deployments[1]
    assert not engine.store.deploy_dir("shop", failed.id).exists()


async def test_static_rollback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeDocker(monkeypatch)
    engine = Engine(Store(tmp_path / "engine"))
    repo = checkout(tmp_path)
    await engine.deploy(repo, "u", "acme/shop", component(), True, quiet)
    await engine.deploy(repo, "u", "acme/shop", component(), True, quiet)
    first, second = engine.store.load("shop").deployments  # type: ignore[union-attr]
    record = await engine.rollback("shop", first.id, quiet)
    assert record.current == first.id and fake.routes == 3
    with pytest.raises(DeployError, match="not a successful deploy"):
        await engine.rollback("shop", "d20990101000000ffff", quiet)


def test_new_deploy_ids_sort_by_time() -> None:
    from datetime import UTC, datetime

    early = new_deploy_id(datetime(2026, 1, 1, tzinfo=UTC))
    late = new_deploy_id(datetime(2026, 1, 2, tzinfo=UTC))
    assert early < late and len(early) == 19


# --- real containers ----------------------------------------------------------------


@pytest.mark.docker
async def test_real_static_deploy_through_router(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Needs Docker. Deploys a static site and fetches it through the router."""
    import urllib.request

    if shutil.which("docker") is None:
        pytest.skip("docker not installed")
    monkeypatch.setenv("DEPLOYSMITH_ROUTER_PORT", "8091")
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text("<h1>sandbox ok</h1>")
    engine = Engine(Store(tmp_path / "engine"))
    static = component(framework="static", build_command=None)
    name, url = await engine.deploy(site, "u", "acme/docker-test", static, True, quiet)
    try:
        request = urllib.request.Request(url, headers={"Host": f"{name}.localhost:8091"})
        with urllib.request.urlopen(request, timeout=10) as response:
            assert b"sandbox ok" in response.read()
    finally:
        await engine.stop(name, delete=True)
        await dk.remove_container("deploysmith-router")
