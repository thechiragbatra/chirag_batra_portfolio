# DeploySmith OS

Personal developer portfolio that doubles as a multi-agent deployment platform.

## Stack
- frontend/: React + Vite + TypeScript + Tailwind + lucide-react (React Flow added in Phase 3)
- backend/: Python 3.11+, FastAPI, LangGraph, pydantic v2
- agents/: Python modules imported by backend (profiler, strategist, provisioner, healer)
- shared/: JSON Schema as source of truth for types shared between Python and TS

## Rules
- Free-tier hosting only: Vercel/Netlify/Cloudflare Pages (frontend), Render/HF Spaces (backend), Neon/Supabase/Turso (DB), or the local sandbox engine. Never route to a paid platform.
- This site itself is hosted on Google Cloud Run (deploy/gcp/), kept inside the free tier: scale to zero, capped instances, no always-on resources. Never add paid GCP services or raise those caps without asking.
- NEVER execute code from a target repo on the host. Clone shallow and analyze statically.
  The only exception is the sandbox engine (agents/sandbox/): repo code (install, build,
  run) may execute solely inside its hardened Docker containers (non-root, all caps
  dropped, no-new-privileges, resource limits, no host mounts except a per-deploy copy;
  install on the default bridge because it needs package registries, build with no
  network, internal-only network at runtime). Never weaken those flags.
- No secrets in code or git. Use .env + .env.example. All API keys are read from env.
- Verify before declaring done: run linters, tests, and the dev servers. Show me the output.
- Keep changes small and commit per logical step. Ask before adding dependencies not listed here.
- Add type hints everywhere; add pytest tests for every agent function.
