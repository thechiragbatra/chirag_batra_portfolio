# shared/

JSON Schemas (draft 2020-12) for the data that crosses the Python/TypeScript boundary.
**These files are the source of truth.**

| Schema | Describes | Python | TypeScript |
| --- | --- | --- | --- |
| `schemas/state.schema.json` | `DeploymentState` and its parts | `agents/models.py` | `frontend/src/types/events.ts` |
| `schemas/event.schema.json` | SSE events from `GET /api/deployments/{id}/events` | `backend/events.py` | `frontend/src/types/events.ts` |

## How the types stay in sync

1. **Change the schema first.** Edit the JSON in `schemas/`.
2. **Update the pydantic models** to match. `backend/tests/test_schema_sync.py` compares the
   models' generated schema (serialization mode) against these files: property names,
   required fields, types, enums, consts and numeric bounds. Any drift fails `pytest`.
3. **Update `frontend/src/types/events.ts`** by hand. Nothing checks this side
   automatically yet. Keep the file a 1:1 mirror: same names, and every field required,
   because the backend always sends every field (nullable fields are `T | null`, never optional).

Wire conventions:

- Every field is always present in JSON. Optional values are sent as `null`.
- Enums are lowercase strings (`"running"`, `"cloudflare_pages"`).
- Timestamps are ISO 8601 UTC strings.
- `Platform` lists free-tier hosts only. Adding a paid platform is a schema change and needs review.

If the manual TypeScript step becomes a burden, generate `events.ts` from these schemas
(e.g. with `json-schema-to-typescript`). That dependency was left out of Phase 1.
