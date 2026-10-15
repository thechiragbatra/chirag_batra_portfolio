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
from agents.sandbox import router as router_mod
from agents.sandbox.engine import DeployError, Engine, find_output_dir
from agents.sandbox.recipes import UnsupportedComponent, recipe_for
from agents.sandbox.router import ROUTER_NAME, app_url, sites_config
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
        f"--user {dk.SANDBOX_UID}",
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
    assert not dk.SANDBOX_UID.startswith("0:")  # never root
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
    assert site.read_text().startswith("build") and fake.routes == 2  # fail-fast + switch
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
    assert record.current == first.id and fake.routes == 5
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


# --- router lifecycle (scripted docker CLI) -----------------------------------------


class FakeCLI:
    """Scripted `docker` CLI: a router that may be running with a given port and mounts."""

    def __init__(
        self,
        running: bool,
        port: str = "8080",
        mounts: str = "",
        run_result: tuple[int, str] = (0, "abc123"),
    ) -> None:
        self.running, self.port, self.mounts, self.run_result = running, port, mounts, run_result
        self.calls: list[tuple[str, ...]] = []

    async def __call__(self, *args: str, timeout: float = 60.0) -> tuple[int, str]:
        self.calls.append(args)
        if args[0] == "inspect" and args[-1] == ROUTER_NAME:
            if not self.running:
                return 1, "Error: No such object"
            if "State.Running" in args[2]:
                return 0, "true"
            return 0, f"{self.port} {self.mounts}"
        if args[0] == "run":
            self.running = True
            return self.run_result
        if args[0] == "rm":
            self.running = False
            return 0, ""
        return 0, ""

    def verbs(self) -> list[str]:
        return [" ".join(c[:2]) if c[0] == "network" else c[0] for c in self.calls]


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch) -> Any:
    def make(**kwargs: Any) -> FakeCLI:
        fake = FakeCLI(**kwargs)
        monkeypatch.setattr(dk, "docker", fake)
        monkeypatch.setattr(router_mod, "docker", fake)
        return fake

    return make


def _mounts(store: Store) -> str:
    return f"{store.router_dir / 'nginx.conf'};{store.router_dir};{store.root / 'apps'};"


async def test_reload_router_reuses_matching_router(tmp_path: Path, cli: Any) -> None:
    store = Store(tmp_path)
    fake = cli(running=True, mounts=_mounts(store))
    await router_mod.reload_router(store)
    assert "run" not in fake.verbs() and "rm" not in fake.verbs()
    assert ("exec", ROUTER_NAME, "nginx", "-s", "reload") in fake.calls
    assert (store.router_dir / "sites.conf").is_file()


@pytest.mark.parametrize("stale", [{"port": "9999"}, {"mounts": "/elsewhere/apps;"}])
async def test_reload_router_recreates_stale_router(
    tmp_path: Path, cli: Any, stale: dict[str, str]
) -> None:
    store = Store(tmp_path)
    fake = cli(running=True, **{"mounts": _mounts(store), **stale})
    await router_mod.reload_router(store)
    verbs = fake.verbs()
    assert verbs.index("rm") < verbs.index("run") < verbs.index("network connect")


async def test_reload_router_tolerates_concurrent_creation(tmp_path: Path, cli: Any) -> None:
    conflict = (125, 'docker: Conflict. The container name "/deploysmith-router" is already in use')
    fake = cli(running=False, run_result=conflict)
    await router_mod.reload_router(Store(tmp_path))
    assert "run" in fake.verbs() and ("exec", ROUTER_NAME, "nginx", "-s", "reload") in fake.calls


async def test_reload_router_reports_start_failure(tmp_path: Path, cli: Any) -> None:
    cli(running=False, run_result=(125, "docker: port is already allocated"))
    with pytest.raises(dk.SandboxError, match="could not start the router"):
        await router_mod.reload_router(Store(tmp_path))


# --- review fixes -------------------------------------------------------------------


def test_find_output_dir_ignores_symlinked_browser_dir(tmp_path: Path) -> None:
    host = tmp_path / "host-project"
    host.mkdir()
    (host / "index.html").write_text("x")
    (host / ".env").write_text("SECRET=1")
    work = tmp_path / "work"
    (work / "dist" / "app").mkdir(parents=True)
    os.symlink(host, work / "dist" / "app" / "browser")
    assert find_output_dir(work) is None


def test_copy_refuses_symlinked_or_escaping_source(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "index.html").write_text("x")
    build = tmp_path / "build"
    build.mkdir()
    os.symlink(outside, build / "dist")
    with pytest.raises(ValueError, match="symlink"):
        copy_tree_without_links(build / "dist", tmp_path / "out", 10_000, build)
    with pytest.raises(ValueError, match="escapes"):
        copy_tree_without_links(outside, tmp_path / "out2", 10_000, build)


def test_node_server_install_keeps_dev_dependencies() -> None:
    comp = component(kind="backend", framework="next", start_command="npm start")
    recipe = recipe_for(comp)
    assert "NODE_ENV" not in recipe.env
    assert recipe.run_env["NODE_ENV"] == "production"


def test_pnpm_server_without_build_installs_with_pnpm() -> None:
    comp = component(
        kind="backend", framework="express", build_command=None, start_command="pnpm start"
    )
    recipe = recipe_for(comp)
    assert recipe.install == "corepack pnpm install --frozen-lockfile"
    assert recipe.start == "corepack pnpm start"


def test_python_requirements_only_without_build_backend() -> None:
    from agents.sandbox.recipes import python_requirements

    uv_style = '[project]\nname="x"\ndependencies=["fastapi>=0.110", "sqlmodel", "--index-url=http://evil"]\n'
    assert python_requirements(uv_style) == ["fastapi>=0.110", "sqlmodel"]
    with_backend = uv_style + '[build-system]\nrequires=["hatchling"]\n'
    assert python_requirements(with_backend) is None
    assert python_requirements("not = [toml") is None


def test_copy_keeps_executable_bit(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    script = src / "build.sh"
    script.write_text("#!/bin/sh\necho hi\n")
    script.chmod(0o4755)  # setuid must not survive
    copy_tree_without_links(src, tmp_path / "out", 10_000)
    mode = (tmp_path / "out" / "build.sh").stat().st_mode & 0o7777
    assert mode == 0o755


# --- review fixes, round 2 ------------------------------------------------------------


def _dep(i: int, status: str, mode: str = "static") -> Deployment:
    return Deployment(
        id=f"d2026010100000{i}abcd",
        created_at="2026-01-01T00:00:00Z",
        status=status,
        mode=mode,
        component=component(),
    )  # type: ignore[arg-type]


def test_prune_never_evicts_successful_deploys_for_failed_ones(tmp_path: Path) -> None:
    store = Store(tmp_path)
    deploys = [
        _dep(0, "ready"),
        _dep(1, "ready"),
        _dep(2, "ready"),
        _dep(3, "failed"),
        _dep(4, "failed"),
        _dep(5, "failed"),
        _dep(6, "failed"),
        _dep(7, "ready"),
    ]
    record = AppRecord(
        name="shop",
        repo_url="u",
        component="web",
        mode="static",
        current=deploys[7].id,
        deployments=deploys,
    )
    for d in deploys:
        store.deploy_dir("shop", d.id).mkdir(parents=True)
    store.prune(record, keep=3)
    kept = [d.id[-5] for d in sorted(record.deployments, key=lambda d: d.id)]
    assert kept == ["1", "2", "4", "5", "6", "7"]  # 3 newest ready + 3 newest failed


def test_corrupt_record_is_skipped_by_list_and_named_by_load(tmp_path: Path) -> None:
    from agents.sandbox.store import CorruptRecord

    store = Store(tmp_path)
    store.save(_record(1, current=0))
    bad = tmp_path / "apps" / "broken"
    bad.mkdir(parents=True)
    (bad / "app.json").write_text("{not json")
    assert [r.name for r in store.list()] == ["shop"]
    with pytest.raises(CorruptRecord, match="broken"):
        store.load("broken")


def test_built_app_ignores_public_and_committed_dist(tmp_path: Path) -> None:
    from agents.sandbox.engine import _output_snapshot

    (tmp_path / "public").mkdir()
    (tmp_path / "public" / "index.html").write_text("vite input")
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist" / "index.html").write_text("stale, committed")
    (tmp_path / "index.html").write_text("vite root")
    before = _output_snapshot(tmp_path)
    assert find_output_dir(tmp_path, built=True, before=before) is None
    # The build rewrites dist/: now it counts.
    import os as _os
    import time as _time

    index = tmp_path / "dist" / "index.html"
    index.write_text("fresh")
    _os.utime(index, (_time.time() + 5, _time.time() + 5))
    assert find_output_dir(tmp_path, built=True, before=before) == tmp_path / "dist"
    # A plain static site (no build) is served from its root.
    assert find_output_dir(tmp_path / "public") == tmp_path / "public"


def test_router_serves_live_deploy_mode_not_record_mode() -> None:
    live = _dep(0, "ready", mode="static")
    record = AppRecord(
        name="blog",
        repo_url="u",
        component="web",
        mode="server",
        current=live.id,
        deployments=[live, _dep(1, "failed", mode="server")],
    )
    config = sites_config([record])
    assert "root /srv/apps/blog/" in config and "proxy_pass" not in config
    assert "proxy_set_header Host $http_host;" in sites_config(
        [
            AppRecord(
                name="api",
                repo_url="u",
                component="api",
                mode="server",
                current=_dep(2, "ready", "server").id,
                deployments=[_dep(2, "ready", "server")],
            )
        ]
    )


async def test_router_failure_after_build_keeps_previous_live(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    FakeDocker(monkeypatch)
    engine = Engine(Store(tmp_path / "engine"))
    repo = checkout(tmp_path)
    await engine.deploy(repo, "u", "acme/shop", component(), True, quiet)
    live = engine.store.load("shop").current  # type: ignore[union-attr]
    calls = {"n": 0}

    async def flaky_reload(_: Store) -> None:
        calls["n"] += 1
        if calls["n"] == 2:  # fail-fast check passes, the post-build switch fails
            raise dk.SandboxError("could not start the router: port is already allocated")

    monkeypatch.setattr(engine_mod, "reload_router", flaky_reload)
    with pytest.raises(DeployError, match="DEPLOYSMITH_ROUTER_PORT"):
        await engine.deploy(repo, "u", "acme/shop", component(), True, quiet)
    record = engine.store.load("shop")
    assert record and record.current == live and record.deployments[-1].status == "failed"


async def test_same_repo_name_from_another_owner_gets_its_own_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    FakeDocker(monkeypatch)
    engine = Engine(Store(tmp_path / "engine"))
    repo = checkout(tmp_path)
    a, _ = await engine.deploy(
        repo, "https://github.com/acme/shop", "acme/shop", component(), True, quiet
    )
    b, _ = await engine.deploy(
        repo, "https://github.com/evil/shop", "evil/shop", component(), True, quiet
    )
    assert (a, b) == ("shop", "evil-shop")
    assert engine.store.load("shop").repo_url == "https://github.com/acme/shop"  # type: ignore[union-attr]


async def test_stop_and_rollback_refuse_while_a_deploy_runs(tmp_path: Path) -> None:
    engine = Engine(Store(tmp_path))
    async with engine._lock("shop"):
        with pytest.raises(DeployError, match="in progress"):
            await engine.stop("shop")
        with pytest.raises(DeployError, match="in progress"):
            await engine.rollback("shop", "d20260101000000abcd", quiet)


async def test_stop_changes_nothing_when_docker_is_down(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path)
    store.save(_record(1, current=0))

    async def down() -> None:
        raise dk.SandboxError("Docker is not running; start Docker Desktop and retry")

    monkeypatch.setattr(dk, "ensure_docker", down)
    with pytest.raises(dk.SandboxError):
        await Engine(store).stop("shop", delete=True)
    assert store.load("shop") is not None


async def test_reconcile_marks_interrupted_builds_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path)
    record = _record(1, current=0)
    record.deployments.append(_dep(9, "building"))
    store.save(record)

    async def down() -> None:
        raise dk.SandboxError("down")

    monkeypatch.setattr(dk, "ensure_docker", down)
    actions = await Engine(store).reconcile()
    assert actions and store.load("shop").deployments[-1].status == "failed"  # type: ignore[union-attr]
    assert "interrupted" in (store.load("shop").deployments[-1].error or "")  # type: ignore[union-attr]


async def test_failed_step_still_removes_its_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    FakeDocker(monkeypatch, fail_on="npm run build")
    removed: list[str] = []

    async def record_rm(name: str) -> None:
        removed.append(name)

    monkeypatch.setattr(dk, "remove_container", record_rm)
    engine = Engine(Store(tmp_path / "engine"))
    with pytest.raises(DeployError):
        await engine.deploy(checkout(tmp_path), "u", "acme/shop", component(), True, quiet)
    assert any(n.endswith("-install") for n in removed) and any(
        n.endswith("-build") for n in removed
    )


async def test_run_streaming_survives_very_long_lines() -> None:
    import sys as _sys

    lines: list[str] = []

    async def keep(line: str) -> None:
        lines.append(line)

    code = await dk.run_streaming(
        [_sys.executable, "-c", "print('x' * 200000); print('done')"], keep, timeout=20
    )
    assert code == 0 and lines[-1] == "done" and sum(len(x) for x in lines[:-1]) == 200000


def test_node_package_caches_live_on_disk_not_tmpfs() -> None:
    env = recipe_for(component(build_command="yarn run build")).env
    assert env["YARN_CACHE_FOLDER"].startswith("/app/.deploysmith/cache")
    assert env["npm_config_cache"].startswith("/app/.deploysmith/cache")
    assert not any(v.startswith("/tmp") for k, v in env.items() if "cache" in k.lower())


def test_ansi_codes_are_stripped_from_build_output() -> None:
    from agents.sandbox.engine import _ANSI

    assert _ANSI.sub("", "\x1b[36mvite v8\x1b[39m \x1b[2Kbuilding") == "vite v8 building"


@pytest.mark.parametrize(
    "spec, image",
    [
        ('requires-python = ">=3.14,<4.0"', "python:3.14-slim"),
        ('requires-python = ">=3.13"', "python:3.13-slim"),
        ('requires-python = ">=3.10"', None),  # the default 3.12 fits
        ('requires-python = ">=3.9,<3.12"', "python:3.11-slim"),
        ("", None),
    ],
)
def test_python_image_follows_requires_python(spec: str, image: str | None) -> None:
    from agents.sandbox.recipes import python_image_for

    assert python_image_for(f"[project]\nname = 'x'\n{spec}\n") == image


def test_sandbox_uid_uses_host_user_on_linux_but_never_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dk.sys, "platform", "linux")
    monkeypatch.setattr(dk.os, "getuid", lambda: 1001)
    monkeypatch.setattr(dk.os, "getgid", lambda: 121)
    assert dk.sandbox_uid() == "1001:121"
    monkeypatch.setattr(dk.os, "getuid", lambda: 0)
    assert dk.sandbox_uid() == "1000:1000"
    monkeypatch.setattr(dk.sys, "platform", "darwin")
    monkeypatch.setattr(dk.os, "getuid", lambda: 501)
    assert dk.sandbox_uid() == "1000:1000"
