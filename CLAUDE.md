# DeploySmith OS

Personal developer portfolio that doubles as a multi-agent deployment platform.

## Stack
- frontend/: React + Vite + TypeScript + Tailwind + lucide-react (React Flow added in Phase 3)
- backend/: Python 3.11+, FastAPI, LangGraph, pydantic v2
- agents/: Python modules imported by backend (profiler, strategist, provisioner, healer)
- shared/: JSON Schema as source of truth for types shared between Python and TS

## Rules
- Free-tier hosting only: Vercel/Netlify/Cloudflare Pages (frontend), Render/HF Spaces (backend), Neon/Supabase/Turso (DB). Never route to a paid platform.
- NEVER execute code from a target repo. Clone shallow and analyze statically only.
- No secrets in code or git. Use .env + .env.example. All API keys are read from env.
- Verify before declaring done: run linters, tests, and the dev servers. Show me the output.
- Keep changes small and commit per logical step. Ask before adding dependencies not listed here.
- Add type hints everywhere; add pytest tests for every agent function.
