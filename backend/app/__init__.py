"""DeploySmith OS API: the FastAPI app (main), its HTTP routers and the services behind them.

    cd backend
    PYTHONPATH=.. uv run uvicorn app.main:app --reload --reload-dir . --reload-dir ../agents

The repo's .env is loaded here, when the package is first imported, so every module reads
its settings after it (shell variables still win).
"""

from app.settings import REPO_ENV_FILE, load_env_file

load_env_file(REPO_ENV_FILE)
