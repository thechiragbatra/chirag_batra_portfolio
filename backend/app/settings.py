"""Settings: the repo's .env, plus the API's host and origin allowlists.

load_env_file puts the repo's .env into the process environment (no dependency needed).

Real environment variables always win, empty values are skipped (so "unset" stays unset),
and DEPLOYSMITH_NO_DOTENV=1 turns it off (the tests set it, so they never pick up keys).
"""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REPO_ENV_FILE = REPO_ROOT / ".env"

# Every state-changing request must carry this header. Browsers cannot attach a custom
# header cross-origin without a CORS preflight, which the origin allowlist rejects, so a
# random web page cannot stop, delete or start deployments on this machine.
CSRF_HEADER = "X-DeploySmith"


def _csv(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def allowed_hosts() -> list[str]:
    """Host header allowlist (blocks DNS rebinding). Set ALLOWED_HOSTS when hosting."""
    return _csv("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")


def cors_origins() -> list[str]:
    return _csv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")


def load_env_file(path: Path) -> list[str]:
    """Set each KEY=value from `path` that is not already set. Returns the keys it set."""
    if os.getenv("DEPLOYSMITH_NO_DOTENV") == "1" or not path.is_file():
        return []
    loaded: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.removeprefix("export ").partition("=")
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key and value and key not in os.environ:
            os.environ[key] = value
            loaded.append(key)
    return loaded
