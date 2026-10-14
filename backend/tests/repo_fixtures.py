"""Build small fake repositories on disk for analyzer tests (no network, no git)."""

import json
from pathlib import Path


def write(root: Path, files: dict[str, str | dict]) -> Path:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content) if isinstance(content, dict) else content)
    return root


VITE_FASTAPI_MONOREPO = {
    ".git/HEAD": "ref: refs/heads/develop\n",
    "README.md": "# shop",
    "frontend/package.json": {
        "scripts": {"dev": "vite", "build": "vite build"},
        "dependencies": {"react": "^19.0.0"},
        "devDependencies": {"vite": "^8.0.0"},
    },
    "frontend/src/main.tsx": "export {}",
    "frontend/src/App.tsx": "export {}",
    "frontend/.env.example": "VITE_API_URL=http://localhost:8000\n",
    "api/requirements.txt": "fastapi>=0.110\nuvicorn[standard]\npsycopg[binary]==3.2  # db\n",
    "api/main.py": "from fastapi import FastAPI\napp = FastAPI()\n",
    "api/.env.example": (
        "# secrets\nDATABASE_URL=postgres://user:secret@localhost/db\nexport SECRET_KEY=abc\n"
    ),
}
