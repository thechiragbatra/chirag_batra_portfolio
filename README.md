# DeploySmith OS

A personal developer portfolio that doubles as a multi-agent deployment platform. Paste a
GitHub repo URL and four agents (profiler, strategist, provisioner, healer) plan and deploy
it to free-tier hosting, streaming every step to the browser.

**Status:** the profiler, strategist and healer are real. The profiler shallow-clones the repo
and analyzes it statically, the strategist picks a free-tier platform per component, and the
healer probes deployed URLs and diagnoses failures. The provisioner is still a mock, so nothing
is actually deployed; the real healer is therefore opt-in (`REAL_HEALER=1`).

## Layout

| Path | What |
| --- | --- |
| `frontend/` | React + Vite + TypeScript + Tailwind. Routes: `/projects`, `/resume`, `/deployer` |
| `backend/` | FastAPI app, LangGraph pipeline (`graph.py`), in-memory run registry, tests |
| `agents/` | `Agent` protocol (`base.py`), domain models (`models.py`), agents, and `skills/` (clone, analyze, plan) |
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

The backend reads its settings from the process environment (`MOCK_AGENTS`, `CORS_ORIGINS`,
`MOCK_AGENT_DELAY`, `MOCK_HEALER_FAILURES`, `REAL_HEALER`; see `.env.example`). `MOCK_AGENTS=1` runs fully
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

## Checks

```sh
cd frontend && npm run lint && npm run build
cd backend && uv run pytest              # offline; add -m network for the real-clone test
cd backend && uvx ruff check . ../agents && uvx ruff format --check . ../agents
```

## API

| Method | Path | |
| --- | --- | --- |
| `POST` | `/api/deployments` | Body `{"repo_url": "https://github.com/<owner>/<repo>"}` → `201 {"id", "repo_url"}`; `422` if not a GitHub repo URL |
| `GET` | `/api/deployments/{id}/events` | SSE stream of `status`, `log`, then a final `done` or `error` event. Supports `Last-Event-ID` replay |
| `GET` | `/api/health` | Liveness |

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
- Each agent implements `Agent.run(state, log) -> partial update` (`agents/base.py`). The graph
  wrapper owns status events, the repair counter and error handling, so the real agents can
  replace the mocks without changing the graph.
- An agent that raises is marked `failed` and the run ends. After 3 unsuccessful repairs, the
  healer is marked `failed`.
- Runs live in memory (last 100). Restarting the backend forgets them.

## Ground rules

See [CLAUDE.md](CLAUDE.md). In short: free-tier platforms only, never execute code from a
target repo, and no secrets in git.
