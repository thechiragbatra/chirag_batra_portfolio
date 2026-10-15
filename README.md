# DeploySmith OS

A personal developer portfolio that doubles as a multi-agent deployment platform. Paste a
GitHub repo URL and four agents (profiler, strategist, provisioner, healer) plan and deploy
it to free-tier hosting, streaming every step to the browser.

**Status:** with `SANDBOX_ENGINE=1` the whole pipeline is real: the profiler shallow-clones and
analyzes the repo, the strategist plans, the provisioner builds each app in a hardened Docker
container and serves it at `http://<app>.localhost:8080`, and the healer probes it. The Apps page
lists every deploy with its build log, one-click rollback and stop. Without that flag the
provisioner is a mock (nothing is deployed) and the real healer is opt-in via `REAL_HEALER=1`.

## Layout

| Path | What |
| --- | --- |
| `frontend/` | React + Vite + TypeScript + Tailwind. Routes: `/projects`, `/resume`, `/deployer`, `/apps` |
| `backend/` | FastAPI app, LangGraph pipeline (`graph.py`), in-memory run registry, apps API (`apps.py`), tests |
| `agents/` | `Agent` protocol (`base.py`), domain models (`models.py`), agents, `skills/` (clone, analyze, plan, probe, diagnose) and `sandbox/` (the local deployment engine) |
| `shared/` | JSON Schemas for state and events, the source of truth for both languages ([shared/README.md](shared/README.md)) |

## Running locally

Requires Node 20+, Python 3.11+, [uv](https://docs.astral.sh/uv/) and `git`.

```sh
cp .env.example .env          # optional: every value has a sensible default

# Backend → http://localhost:8000
cd backend
uv sync
PYTHONPATH=.. uv run uvicorn main:app --reload --reload-dir . --reload-dir ../agents

# Frontend → http://localhost:5173 (in a second terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173/deployer and submit a public repo such as
`https://github.com/fastapi/full-stack-fastapi-template`.

### Sandbox engine (real deploys, $0)

With Docker Desktop running, start the backend with `SANDBOX_ENGINE=1` instead:

```sh
SANDBOX_ENGINE=1 PYTHONPATH=.. uv run uvicorn main:app --reload --reload-dir . --reload-dir ../agents
```

Now a deploy really builds the repo and serves it. Try `https://github.com/octocat/Spoon-Knife`
(static) or a small Vite, Express, FastAPI, Flask, Streamlit or Gradio app. Static output is
served from an immutable per-deploy directory; servers run as containers behind the router.
Manage everything on http://localhost:5173/apps. Engine state lives in `.deploysmith/` (ignored
by git); `docker ps --filter label=dev.deploysmith.engine=1` shows what is running.

Things to know:

- The first deploy pulls about 500 MB of base images (`node:22-alpine`, `python:3.12-slim`,
  `nginx:1.27-alpine`), so its install step looks slow.
- Run **one sandbox backend per machine**: the router container and the apps network are
  shared. `pytest -m docker` also restarts the router, so live apps go dark until the next
  deploy, rollback or backend restart.
- On restart the backend reconciles: deploys interrupted mid-build are marked failed, and
  live server containers that are down are started again.
- To tear everything down:

  ```sh
  docker rm -f $(docker ps -aq --filter label=dev.deploysmith.engine=1)
  docker network rm deploysmith-apps
  rm -rf .deploysmith
  ```

The backend reads its settings from the process environment (`MOCK_AGENTS`, `CORS_ORIGINS`,
`MOCK_AGENT_DELAY`, `MOCK_HEALER_FAILURES`, `REAL_HEALER`, `SANDBOX_ENGINE`, `ALLOWED_HOSTS`
and the `DEPLOYSMITH_*` engine settings; see `.env.example`). `MOCK_AGENTS=1` runs fully
offline with mock agents. Export them in your shell, or
prefix the uvicorn command, e.g. `MOCK_HEALER_FAILURES=4 PYTHONPATH=.. uv run uvicorn main:app`
to watch the healer exhaust its 3 repair attempts. Vite reads `VITE_API_URL` from the root `.env`.

### Adding portfolio projects

On the local dev server only, `/projects` shows an **Add project** button. Paste a GitHub repo
URL; it fetches the name, description, topics and homepage from the GitHub API, lets you edit
them, then appends the project to `frontend/src/data/projects.json`. Commit that file to publish.
The editor is a Vite dev-server plugin (`frontend/plugins/projectEditor.ts`), so it is absent from
production builds. Set `GITHUB_TOKEN` in `.env` if you hit GitHub's anonymous rate limit
(60 requests/hour).

### Résumé PDF

`frontend/public/resume.pdf` (the site's Download PDF button) is generated from
`frontend/src/data/resume.json`, so edit the JSON and regenerate rather than editing the PDF:

```sh
cd frontend && npm run resume:pdf     # needs Google Chrome; set CHROME=/path/to/chrome elsewhere
```

## Deploying to Google Cloud

The site (frontend + API) deploys to Google Cloud Run with one script; see
[deploy/gcp/README.md](deploy/gcp/README.md):

```sh
GCP_PROJECT=your-project-id ./deploy/gcp/deploy.sh
```

The sandbox engine stays local (Cloud Run has no Docker daemon), so the hosted Deployer
profiles and plans for real and simulates the deploy.

## Checks

```sh
cd frontend && npm run lint && npm run build
cd backend && uv run pytest              # offline; -m network for real clones/probes, -m docker for a real sandbox deploy
cd backend && uvx ruff check . ../agents && uvx ruff format --check . ../agents
```

## API

| Method | Path | |
| --- | --- | --- |
| `POST` | `/api/deployments` | Body `{"repo_url": "https://github.com/<owner>/<repo>"}` → `201 {"id", "repo_url"}`; `422` if not a GitHub repo URL |
| `GET` | `/api/deployments/{id}/events` | SSE stream of `status`, `log`, then a final `done` or `error` event. Supports `Last-Event-ID` replay |
| `GET` | `/api/health` | Liveness |

Every `POST`/`DELETE` must send the header `X-DeploySmith: 1` (otherwise `403`), and requests
with a `Host` outside `ALLOWED_HOSTS` get `400`. Browsers cannot add that header cross-origin
without a CORS preflight, so other web pages cannot drive the API.
| `GET` | `/api/apps` | Sandbox apps with their deploy history (newest first) and live URL, plus `engine_enabled` and `router_running` |
| `GET` | `/api/apps/{name}/deploys/{id}/log` | Build log of one deploy (text, last 2 MB) |
| `POST` | `/api/apps/{name}/rollback` | Body `{"deploy_id"}`: make an earlier successful deploy live again. `404` unknown deploy, `409` not rollback-able or another operation is running, `422` malformed id |
| `POST` | `/api/apps/{name}/stop` | Stop serving the app (deploys are kept); `DELETE /api/apps/{name}` removes it. `503` when Docker is not running (nothing is changed) |

Event and state shapes: [shared/schemas](shared/schemas).

## How the pipeline works

```
profiler → strategist → provisioner → healer ─┐
                             ▲                │ unhealthy and repairs < 3
                             └────────────────┘
```

- **Profiler** (`agents/skills/clone.py`, `analyze.py`): `git clone --depth 1` with HTTPS only,
  no submodules, LFS or hooks, symlinks checked out as plain files, host git config ignored,
  a 60s timeout and a 200 MB cap. Analysis only reads files (`package.json`, `requirements.txt`,
  `pyproject.toml`, `.env.example` names, never values). Nothing from the repo is executed.
- **Strategist** (`agents/skills/plan.py`): deterministic rules, e.g. Vite → Vercel,
  FastAPI → Render, Streamlit → Hugging Face Spaces, Postgres → Neon. Engines with no free
  target (MySQL, MongoDB) are reported in the plan notes rather than placed on a paid host.
- **Healer** (`agents/skills/probe.py`, `diagnose.py`): an HTTPS GET per deployed component,
  only to hosts on `*.vercel.app`, `*.netlify.app`, `*.pages.dev`, `*.onrender.com` or
  `*.hf.space` (no proxies, redirects off those domains are not followed, 2 KB body cap).
  Databases are skipped. Render and HF Spaces get one slower retry for free-tier cold starts.
  Failures map to fixes from the status code and platform headers, e.g. Vercel
  `DEPLOYMENT_NOT_FOUND`, a redirect to the Vercel login (Deployment Protection), Render
  `no-server`, or a Render 502 (bind to `0.0.0.0:$PORT`).
- **Sandbox engine** (`agents/sandbox/`): the only place repo code runs, and only inside Docker.
  `docker.py` starts every container non-root with all capabilities dropped, no-new-privileges,
  a read-only root filesystem, memory/CPU/PID limits, no network during builds and an
  internal-only network at runtime; the per-deploy source copy is the sole mount. `recipes.py`
  maps each framework to install/build/start commands, `store.py` keeps immutable deploy
  directories and build logs under `.deploysmith/`, `router.py` generates the config for an
  unprivileged nginx on `127.0.0.1:8080` (static files or a proxy to the app container), and
  `engine.py` runs the deploy: a failed build never replaces the live deploy, a server must
  answer HTTP before traffic switches, and rollback just re-points the router. On a repair
  only components a redeploy can fix (no response, gateway errors, no live deploy) are
  redeployed; a failed build or an app answering with its own error ends the run with a
  clear message, since the source has not changed. Retention keeps the newest successful
  deploys as rollback targets; failed ones never push them out.
- Each agent implements `Agent.run(state, log) -> partial update` (`agents/base.py`). The graph
  wrapper owns status events, the repair counter and error handling, so the real agents can
  replace the mocks without changing the graph.
- An agent that raises is marked `failed` and the run ends. After 3 unsuccessful repairs, the
  healer is marked `failed`.
- Runs live in memory (last 100). Restarting the backend forgets them.

## Ground rules

See [CLAUDE.md](CLAUDE.md). In short: free-tier platforms only, never execute code from a
target repo, and no secrets in git.
