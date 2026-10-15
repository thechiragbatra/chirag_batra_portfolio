"""On-disk state of the sandbox engine: apps, their deploys, and which deploy is live.

Layout under the engine root (DEPLOYSMITH_ENGINE_DIR, default <repo>/.deploysmith):

    apps/<app>/app.json            AppRecord (atomic writes)
    apps/<app>/deploys/<id>/       one immutable directory per deploy
    apps/<app>/logs/<id>.log       full build log
    router/default.conf            generated nginx config

A deploy directory is never rewritten after it is built, so rollback is just
pointing `current` at an older one, the same model Vercel uses.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import shutil
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from agents.models import Component

logger = logging.getLogger(__name__)

KEEP_FAILED = 3
MAX_FILES = 200_000
MAX_APP_NAME = 40
_APP_NAME = re.compile(rf"^[a-z0-9](?:[a-z0-9-]{{0,{MAX_APP_NAME - 2}}}[a-z0-9])?$")
_DEPLOY_ID = re.compile(r"^d[0-9]{14}[0-9a-f]{4}$")

DeployStatus = Literal["building", "ready", "failed"]
Mode = Literal["static", "server"]


def keep_deploys() -> int:
    """Successful deploys retained per app (rollback targets), DEPLOYSMITH_KEEP_DEPLOYS."""
    return max(1, int(os.getenv("DEPLOYSMITH_KEEP_DEPLOYS", "3")))


class CorruptRecord(ValueError):
    """An app.json that no longer parses (hand-edited, or written by an older version)."""


def default_root() -> Path:
    configured = os.getenv("DEPLOYSMITH_ENGINE_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / ".deploysmith"


def app_name(repo_name: str, component: str, single: bool, with_owner: bool = False) -> str:
    """A DNS-label-safe name: 'acme/My_Shop' + 'api' -> 'my-shop-api' (or 'my-shop').

    with_owner prefixes the GitHub owner ('acme-my-shop'), used when another repo with
    the same name already owns the short name.
    """
    base = repo_name.replace("/", "-") if with_owner else repo_name.rsplit("/", 1)[-1]
    raw = base if single else f"{base}-{component}"
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")[:MAX_APP_NAME].strip("-")
    return slug or "app"


def new_deploy_id(now: datetime | None = None) -> str:
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%d%H%M%S")
    return f"d{stamp}{secrets.token_hex(2)}"


def container_name(app: str, deploy_id: str) -> str:
    return f"ds-{app}-{deploy_id}"


class Deployment(BaseModel):
    id: str
    created_at: datetime
    status: DeployStatus
    mode: Mode
    component: Component
    # The image the deploy was built with, so a rollback runs it on the same runtime
    # even after the engine's default image changes. None in records from older versions.
    image: str | None = None
    error: str | None = None


class AppRecord(BaseModel):
    name: str
    repo_url: str
    component: str
    framework: str | None = None
    mode: Mode
    current: str | None = None
    deployments: list[Deployment] = Field(default_factory=list)

    def deployment(self, deploy_id: str) -> Deployment | None:
        return next((d for d in self.deployments if d.id == deploy_id), None)


class Store:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or default_root()).resolve()

    # --- paths (every name is validated before it touches the filesystem) ---------

    def app_dir(self, app: str) -> Path:
        if not _APP_NAME.match(app):
            raise ValueError(f"invalid app name: {app!r}")
        return self.root / "apps" / app

    def deploy_dir(self, app: str, deploy_id: str) -> Path:
        if not _DEPLOY_ID.match(deploy_id):
            raise ValueError(f"invalid deploy id: {deploy_id!r}")
        return self.app_dir(app) / "deploys" / deploy_id

    def log_path(self, app: str, deploy_id: str) -> Path:
        self.deploy_dir(app, deploy_id)  # validates both names
        return self.app_dir(app) / "logs" / f"{deploy_id}.log"

    @property
    def router_dir(self) -> Path:
        return self.root / "router"

    # --- records ----------------------------------------------------------------

    def load(self, app: str) -> AppRecord | None:
        path = self.app_dir(app) / "app.json"
        if not path.is_file():
            return None
        try:
            return AppRecord.model_validate_json(path.read_text())
        except (ValidationError, ValueError, OSError) as exc:
            raise CorruptRecord(
                f"{path} cannot be read ({type(exc).__name__}); fix or delete it"
            ) from exc

    def save(self, record: AppRecord) -> None:
        directory = self.app_dir(record.name)
        directory.mkdir(parents=True, exist_ok=True)
        tmp = directory / "app.json.tmp"
        tmp.write_text(record.model_dump_json(indent=2))
        os.replace(tmp, directory / "app.json")

    def list(self) -> list[AppRecord]:
        apps_root = self.root / "apps"
        if not apps_root.is_dir():
            return []
        records: list[AppRecord] = []
        for path in sorted(apps_root.iterdir()):
            if not _APP_NAME.match(path.name):
                continue
            try:
                record = self.load(path.name)
            except CorruptRecord as exc:
                # One unreadable record must not hide every other app or break the router.
                logger.warning("skipping app %s: %s", path.name, exc)
                continue
            if record is not None:
                records.append(record)
        return records

    def delete(self, app: str) -> None:
        shutil.rmtree(self.app_dir(app), ignore_errors=True)

    def prune(self, record: AppRecord, keep: int | None = None) -> list[str]:
        """Keep the newest `keep` successful deploys plus the live one, and the newest
        KEEP_FAILED failed ones (their logs are what explains them). Returns removed ids.

        Failed deploys never count toward `keep`, so a run of broken builds cannot evict
        the rollback targets.
        """
        keep = keep if keep is not None else keep_deploys()
        newest = sorted(record.deployments, key=lambda d: d.id, reverse=True)
        ready = [d for d in newest if d.status == "ready"]
        failed = [d for d in newest if d.status == "failed"]
        building = [d for d in newest if d.status == "building"]
        keep_ids = {d.id for d in ready[:keep] + failed[:KEEP_FAILED] + building}
        if record.current:
            keep_ids.add(record.current)
        removed = [d.id for d in record.deployments if d.id not in keep_ids]
        for deploy_id in removed:
            shutil.rmtree(self.deploy_dir(record.name, deploy_id), ignore_errors=True)
            self.log_path(record.name, deploy_id).unlink(missing_ok=True)
        record.deployments = [d for d in record.deployments if d.id in keep_ids]
        return removed


def copy_tree_without_links(
    src: Path, dest: Path, max_bytes: int, within: Path | None = None
) -> int:
    """Copy regular files only. Symlinks made inside a container could point at host
    paths once outside it, so they are dropped rather than followed. Returns bytes copied.

    os.walk always opens `src` itself, so `src` must not be a link and, when `within` is
    given, must resolve inside it; otherwise a build could publish an arbitrary host dir.
    """
    if src.is_symlink():
        raise ValueError("refusing to copy through a symlink")
    if within is not None and not src.resolve().is_relative_to(within.resolve()):
        raise ValueError("output directory escapes the build tree")
    total = files = 0
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        current = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not (current / d).is_symlink() and d != ".git"]
        target = dest / current.relative_to(src)
        target.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            path = current / name
            if path.is_symlink() or not path.is_file():
                continue
            info = path.stat()
            total += info.st_size
            files += 1
            if total > max_bytes:
                raise ValueError(f"tree exceeds {max_bytes // (1024 * 1024)} MB")
            if files > MAX_FILES:
                raise ValueError(f"tree has more than {MAX_FILES:,} files")
            shutil.copyfile(path, target / name, follow_symlinks=False)
            # Keep the executable bit (scripts the build or start command runs), never setuid.
            os.chmod(target / name, stat.S_IMODE(info.st_mode) & 0o755 | 0o644)
    return total
