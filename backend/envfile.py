"""Load the repo's .env into the process environment (no dependency needed).

Real environment variables always win, empty values are skipped (so "unset" stays unset),
and DEPLOYSMITH_NO_DOTENV=1 turns it off (the tests set it, so they never pick up keys).
"""

from __future__ import annotations

import os
from pathlib import Path


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
