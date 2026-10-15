# DeploySmith API image (Cloud Run, Azure Container Apps, or any container host).
# Build from the repository root:
#   docker build -f deploy/docker/api.Dockerfile -t deploysmith-api .
#
# The sandbox engine needs a Docker daemon, which Cloud Run does not have, so it stays
# off here: the profiler and strategist are real (git is installed for shallow clones),
# the provisioner and healer are simulated.

FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv

# git for the profiler's hardened shallow clones; nothing from a cloned repo is executed.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/app/.venv/bin:$PATH"

# Dependencies first, so code changes reuse the cached layer.
COPY backend/pyproject.toml backend/uv.lock backend/
RUN cd backend && uv sync --frozen --no-dev --no-install-project

COPY agents agents
COPY backend backend
# The guide agent answers from the site's own content and runs the Churn Lab models.
COPY frontend/src/data frontend/src/data
COPY frontend/public/models frontend/public/models

# Run unprivileged.
RUN useradd --create-home --uid 10001 app
USER app

ENV SANDBOX_ENGINE=0 \
    MOCK_AGENTS=0 \
    REAL_HEALER=0 \
    GUIDE_FEEDBACK_FILE=/tmp/guide-feedback.jsonl \
    PORT=8080
WORKDIR /app/backend
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --timeout-keep-alive 75"]
