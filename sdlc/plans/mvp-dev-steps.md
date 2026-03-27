# MVP Development Steps — Healthcare Data Processing Platform

## Summary

Execution plan for building the MVP from scratch. Steps are grouped by concern and ordered for
sequential execution. Steps 1–4 establish the project skeleton and infrastructure. Steps 5–11
create service stubs. Step 12 completes the Patient API Service orchestrator stub.

All services are FastAPI (Python 3.12+), managed with `uv` and `pyproject.toml` per service.
No ORM — `asyncpg` directly. No implementation logic in stubs — only structure, wiring, and
health checks.

## Assumptions

- Docker Compose is the only runtime for this phase.
- A single Postgres instance with per-service schemas is acceptable for the POC.
- NATS core (no JetStream) is sufficient — no message persistence.
- Python deps per service: `fastapi>=0.111`, `uvicorn[standard]>=0.29`, `nats-py>=2.7`,
  `asyncpg>=0.29`, `pydantic>=2.6`.
- Dev extras per service: `pytest`, `pytest-asyncio`, `httpx`.
- Stub services must boot cleanly, connect to NATS and Postgres, and expose a `/health` endpoint.
  They must NOT implement business logic.

---

## Group 1: Project Skeleton and Infrastructure

### Step 1 — Create monorepo file structure with per-service directories and Dockerfiles

**What to create:**

- Monorepo root with a workspace-level `pyproject.toml` declaring all service sub-packages.
- One directory per service under `services/`:
  - `services/ingestion-gateway/`
  - `services/mpi/`
  - `services/reconciliation/`
  - `services/timeline/`
  - `services/llm-summary/`
  - `services/notification/`
  - `services/patient-api/`
- Inside each service directory:
  - `pyproject.toml` — project metadata and dependencies (see Appendix in architecture doc for
    the canonical template).
  - `Dockerfile` — multi-stage build: `uv sync` in build stage, `uvicorn app.main:app` in run
    stage.
  - `app/` package directory with an empty `__init__.py` and a placeholder `main.py`.
- A top-level `schemas/` directory for internal JSON schema definitions (populated in later steps).
- A top-level `shared/` directory for `message_bus.py` and `cache_service.py` stubs
  (populated in later steps).

**Key files:**

```
pyproject.toml                         # workspace root
schemas/                               # internal event schemas (placeholder)
shared/
  message_bus.py                       # stub
  cache_service.py                     # stub
services/
  ingestion-gateway/
    pyproject.toml
    Dockerfile
    app/__init__.py
    app/main.py
  mpi/
    pyproject.toml
    Dockerfile
    app/__init__.py
    app/main.py
  reconciliation/
    pyproject.toml
    Dockerfile
    app/__init__.py
    app/main.py
  timeline/
    pyproject.toml
    Dockerfile
    app/__init__.py
    app/main.py
  llm-summary/
    pyproject.toml
    Dockerfile
    app/__init__.py
    app/main.py
  notification/
    pyproject.toml
    Dockerfile
    app/__init__.py
    app/main.py
  patient-api/
    pyproject.toml
    Dockerfile
    app/__init__.py
    app/main.py
```

**Notes and constraints:**

- Each `Dockerfile` must use the same base image and `uv` invocation pattern for consistency.
- The workspace root `pyproject.toml` should declare `[tool.uv.workspace]` with `members`
  pointing to each service path.
- Service port assignments (set in Dockerfiles and compose): Ingestion Gateway 8001, MPI 8002,
  Reconciliation 8003, Timeline 8004, LLM Summary 8005, Notification 8006, Patient API 8000.
- `app/main.py` in each service must define a `FastAPI` app with a `lifespan` context manager
  (stub — no real connections yet) and a `GET /health` endpoint returning `{"status": "ok"}`.

---

### Step 2 — Create `docker-compose.yml` for Postgres, NATS, and all services

**What to create:**

- `docker-compose.yml` at the repo root wiring together:
  - `postgres` — official `postgres:16` image, port 5432, volume for data persistence, env vars
    for `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`. Mounts
    `./infra/postgres/init/` as `/docker-entrypoint-initdb.d/` so SQL init files run automatically.
  - `nats` — official `nats:latest` image, port 4222 (client), port 8222 (monitoring).
  - All seven services — each built from its own `Dockerfile`, port-mapped per the assignments in
    Step 1, with `depends_on: [postgres, nats]`, and environment variables for
    `DATABASE_URL` and `NATS_URL`.

**Key files:**

```
docker-compose.yml
infra/
  postgres/
    init/                              # SQL init files mounted here (populated in Steps 3–4)
```

**Notes and constraints:**

- `DATABASE_URL` per service should include the service schema in the connection string or be
  set to the default and have the schema set via `SET search_path` in the service startup code.
- `NATS_URL` for all services: `nats://nats:4222`.
- Use named volumes for Postgres data so `docker-compose down` does not destroy data by default.
- Services should use `restart: unless-stopped` to handle startup ordering races with Postgres
  and NATS.
- The `infra/postgres/init/` directory must contain files named with numeric prefixes so
  Postgres executes them in deterministic order (e.g. `01-users.sql`, `02-tables.sql`).

---

### Step 3 — Create `01-users.sql` — Postgres users and roles

**What to create:**

- `infra/postgres/init/01-users.sql`

**Contents to define:**

- A `write_user` role with `LOGIN`, password, and `CONNECT` on the database.
- A `read_user` role with `LOGIN`, password, and `CONNECT` on the database.
- `GRANT` statements:
  - `write_user`: `SELECT`, `INSERT`, `UPDATE`, `DELETE` on all tables in each service schema
    (schemas defined in Step 4). Also `USAGE` on sequences (for `BIGSERIAL` columns).
  - `read_user`: `SELECT` only on all tables in each service schema.
- `ALTER DEFAULT PRIVILEGES` so future tables in each schema automatically inherit the same grants
  for both roles.

**Key files:**

```
infra/postgres/init/01-users.sql
```

**Notes and constraints:**

- Do not hardcode passwords in the SQL file — use Postgres variables or accept that this is
  a local dev file and use well-known dev credentials (e.g. `devpass`). Document the decision.
- Schemas are created in `02-tables.sql` (Step 4). The `GRANT` statements in this file should
  reference schemas by name — ensure the order of execution is correct (users before tables).
- `ALTER DEFAULT PRIVILEGES` is the preferred approach over per-table grants so new tables
  added during development automatically inherit permissions.
- The `postgres` superuser (from `POSTGRES_USER`) creates these roles and grants.

---

### Step 4 — Create `02-tables.sql` — all service schemas and tables

**What to create:**

- `infra/postgres/init/02-tables.sql`

**Contents to define (one schema block per service):**

- `CREATE SCHEMA IF NOT EXISTS` for each service: `mpi`, `reconciliation`, `timeline`, `llm`,
  `notification`.
- MPI schema tables (from architecture Section 3 and `mvp-tables.md`):
  - `mpi.mpi_source_system`
  - `mpi.mpi_patients`
  - `mpi.mpi_source_identities` with indexes
- Reconciliation schema tables:
  - `reconciliation.reconciliation_events` — raw reconciled events with `canonical_patient_id`,
    `source_system_id`, `event_date`, `status` (active/voided), `version`, `payload JSONB`,
    `created_at`.
  - `reconciliation.processed_messages` — idempotency table: `message_id TEXT PRIMARY KEY`,
    `processed_at TIMESTAMPTZ`, `result_ref TEXT`.
  - `reconciliation.reconciliation_conflicts` — conflict log: `id BIGSERIAL PRIMARY KEY`,
    `canonical_patient_id UUID`, `conflict_type TEXT`, `details JSONB`, `created_at TIMESTAMPTZ`.
- Timeline schema tables:
  - `timeline.llm_pending_assessments` — debounce table: `canonical_patient_id UUID PRIMARY KEY`,
    `scheduled_after TIMESTAMPTZ`, `status TEXT` (pending/processing/done/failed), `created_at`,
    `updated_at`.
  - `timeline.patient_timeline` — materialized view over `reconciliation.reconciliation_events`
    (create the view definition here, using `CREATE MATERIALIZED VIEW ... AS SELECT ...`).
    Requires a unique index for `REFRESH CONCURRENTLY`.
- LLM schema tables:
  - `llm.llm_recommendations` — `id BIGSERIAL PRIMARY KEY`, `canonical_patient_id UUID`,
    `risk_tier TEXT`, `key_risks JSONB`, `recommended_actions JSONB`, `summary TEXT`,
    `model TEXT`, `prompt_version TEXT`, `mode TEXT` (batch/agent), `has_changed_from_last BOOL`,
    `similarity_score NUMERIC`, `output_hash TEXT`, `generated_at TIMESTAMPTZ`.
    Index on `(canonical_patient_id, generated_at DESC)`.
- Ingestion Gateway — no schema/tables required (stateless; publishes to NATS only).
- Notification Service — no tables required for the stub (console log only).
- Patient API Service — no tables required (reads from other service schemas only).

**Key files:**

```
infra/postgres/init/02-tables.sql
```

**Notes and constraints:**

- The `patient_timeline` materialized view must cross schemas (`reconciliation.reconciliation_events`).
  This requires the `timeline` schema to have `SELECT` privilege on the `reconciliation` schema.
  Add the necessary `GRANT SELECT ON ALL TABLES IN SCHEMA reconciliation TO read_user` in `01-users.sql`
  or handle via `ALTER DEFAULT PRIVILEGES`.
- The materialized view requires a unique index to support `REFRESH MATERIALIZED VIEW CONCURRENTLY`.
  Create it immediately after the `CREATE MATERIALIZED VIEW` statement.
- Seed `mpi.mpi_source_system` with the three known sources: `source-a`, `source-b`, `source-c`.
- Follow the exact DDL from `mvp-tables.md` and architecture Section 3 for MPI tables — those
  definitions are already reviewed and corrected.

---

## Group 2: Service Stubs

All stubs in this group follow the same structure:

- `FastAPI` app with a `lifespan` context manager that opens a NATS connection and an `asyncpg`
  pool, stores them on `app.state`, and drains/closes them on shutdown.
- `GET /health` endpoint returning `{"status": "ok", "service": "<service-name>"}`.
- NATS subscriptions declared in `lifespan` but with no-op handlers (log the message, return).
- No business logic. No database writes beyond connection validation (e.g. `SELECT 1`).
- `DATABASE_URL` and `NATS_URL` read from environment variables.

---

### Step 5 — Ingestion Gateway stub

**What to create:**

- `services/ingestion-gateway/app/main.py` — FastAPI app.
- `services/ingestion-gateway/app/routers/ingest.py` — stub router with three POST endpoints:
  - `POST /ingest/source-a`
  - `POST /ingest/source-b`
  - `POST /ingest/source-c`
  Each accepts a JSON body, logs receipt, and returns `{"received": true}`. No NATS publish yet.

**Key files:**

```
services/ingestion-gateway/app/main.py
services/ingestion-gateway/app/routers/ingest.py
```

**Notes and constraints:**

- Ingestion Gateway is stateless — no Postgres connection needed in the stub.
- NATS connection should still be opened in `lifespan` and stored on `app.state.nc` to validate
  the wiring before business logic is added.
- Topics this service will publish to (for documentation only at stub stage):
  `raw.source-a`, `raw.source-b`, `raw.source-c`.
- The `message-id` derivation (`sha256(source_id + version + source_system)`) is not
  implemented in the stub — noted as a TODO comment.

---

### Step 6 — Master Patient Index (MPI) stub

**What to create:**

- `services/mpi/app/main.py` — FastAPI app with `lifespan` opening asyncpg pool.
- `services/mpi/app/routers/internal.py` — stub internal router:
  - `GET /internal/patient/resolve` — accepts `source_system` and `source_patient_id` as query
    params, returns a hardcoded `{"canonical_patient_id": null, "status": "stub"}`.
- NATS subscriptions for `raw.source-a`, `raw.source-b`, `raw.source-c` registered in
  `lifespan` with no-op handlers.

**Key files:**

```
services/mpi/app/main.py
services/mpi/app/routers/internal.py
```

**Notes and constraints:**

- This service subscribes to all three raw topics and also exposes an internal HTTP endpoint.
  Both are stub only at this stage.
- The atomic upsert pattern (`INSERT ... ON CONFLICT DO NOTHING; SELECT ...`) is the critical
  implementation detail — add a TODO comment at the resolve endpoint pointing to architecture
  Section 3.
- The Reconciliation Service calls this endpoint via HTTP with retry/backoff — the stub must
  return a valid JSON response (even if hardcoded) so Reconciliation's future retry logic
  does not error.

---

### Step 7 — Reconciliation Service stub

**What to create:**

- `services/reconciliation/app/main.py` — FastAPI app with `lifespan` opening asyncpg pool and
  NATS connection.
- NATS subscriptions for `raw.source-a`, `raw.source-b`, `raw.source-c` registered in
  `lifespan` with no-op handlers.
- No HTTP endpoints beyond `/health` (Reconciliation is event-driven only).

**Key files:**

```
services/reconciliation/app/main.py
```

**Notes and constraints:**

- The idempotency check against `reconciliation.processed_messages` is not implemented in the
  stub — add a TODO comment.
- The HTTP call to MPI (`GET /internal/patient/resolve`) with exponential backoff retry is not
  implemented — add a TODO comment with the retry schedule from architecture Section 2.
- Publishes to `reconciled.events` — not implemented in stub; noted as TODO.
- Horizontal scaling via consistent hashing on `canonical_patient_id` is a future concern —
  note it as out of scope for MVP.

---

### Step 8 — Timeline Service stub

**What to create:**

- `services/timeline/app/main.py` — FastAPI app with `lifespan` opening asyncpg pool and
  NATS connection.
- NATS subscription for `reconciled.events` registered in `lifespan` with a no-op handler.
- No HTTP endpoints beyond `/health` (Timeline Service is event-driven only).

**Key files:**

```
services/timeline/app/main.py
```

**Notes and constraints:**

- The refresh-then-publish ordering rule is the critical constraint: `REFRESH MATERIALIZED VIEW
  CONCURRENTLY patient_timeline` must complete before `timeline.updated` is published.
  Add a TODO comment with this rule clearly stated.
- The debounce upsert on `timeline.llm_pending_assessments` is not implemented — add a TODO.
- Publishing `timeline.updated` is not implemented — add a TODO.
- `REFRESH MATERIALIZED VIEW CONCURRENTLY` requires a unique index on `patient_timeline` —
  confirm the index exists in `02-tables.sql` (Step 4).

---

### Step 9 — LLM Summary Service stub

**What to create:**

- `services/llm-summary/app/main.py` — FastAPI app with `lifespan` opening asyncpg pool and
  NATS connection.
- `services/llm-summary/app/backends/llm_backend.py` — abstract `LLMBackend` interface stub:
  ```
  class LLMBackend:
      async def complete(self, prompt: str, context: dict) -> AsyncIterator[str]: ...
  ```
- `services/llm-summary/app/backends/demo_backend.py` — `DemoBackend` stub that returns an
  empty async iterator. This is the swappable implementation (future: Ollama, LangGraph, Claude API).
- NATS subscription for `timeline.updated` registered in `lifespan` with a no-op handler.
- No HTTP endpoints beyond `/health`.

**Key files:**

```
services/llm-summary/app/main.py
services/llm-summary/app/backends/llm_backend.py
services/llm-summary/app/backends/demo_backend.py
```

**Notes and constraints:**

- The `LLMBackend` interface must match the contract in architecture Section 6:
  `complete(prompt: str, context: dict) -> AsyncIterator[str]`.
- The cron scheduler (every 12 hours, drains `llm_pending_assessments`) is not implemented in
  the stub — add a TODO comment referencing Section 6 batch mode steps.
- The deduplication write path (hash check → structural diff → cosine similarity) is not
  implemented — add a TODO.
- MVP default is hash check only. Structural diff and cosine are extension points — note this.
- `pyproject.toml` for this service may need an additional dep (`anthropic` or `httpx`) in the
  future — leave a comment noting this.

---

### Step 10 — Notification Service stub

**What to create:**

- `services/notification/app/main.py` — FastAPI app with `lifespan` opening NATS connection
  (no Postgres pool needed — this service is stateless for the stub).
- NATS subscription for `risk.computed` registered in `lifespan` with a no-op handler that
  logs the message to stdout.
- No HTTP endpoints beyond `/health`.

**Key files:**

```
services/notification/app/main.py
```

**Notes and constraints:**

- Notification Service has no database tables — it consumes events and logs/webhooks only.
  No asyncpg pool is needed in the stub.
- The alert routing logic (High/Critical risk tier → console log or webhook) is not implemented —
  add a TODO comment.
- The webhook destination is not configured — add a `WEBHOOK_URL` env var placeholder in
  `docker-compose.yml` (empty by default).

---

### Step 11 — Patient API Service stub

**What to create:**

- `services/patient-api/app/main.py` — FastAPI app with `lifespan`. No NATS connection (Patient
  API is HTTP-only). No Postgres pool (reads via downstream service calls, not direct DB access).
- `services/patient-api/app/routers/patients.py` — stub router with all six endpoints returning
  placeholder responses:
  - `GET /v1/patient/{canonical_patient_id}/info` → `{"stub": true}`
  - `GET /v1/patient/{canonical_patient_id}/timelines` → `{"stub": true}`
  - `GET /v1/patient/{canonical_patient_id}/recommendation` → `{"stub": true}`
  - `GET /v1/patient/{canonical_patient_id}/recommendations` → `{"stub": true}`
  - `GET /v1/patient/{canonical_patient_id}/conflicts` → `{"stub": true}`
  - `POST /v1/patient/recommendations` → `{"stub": true}`

**Key files:**

```
services/patient-api/app/main.py
services/patient-api/app/routers/patients.py
```

**Notes and constraints:**

- Patient API does not own any DB tables — it orchestrates reads from downstream services.
  In the POC, these are direct in-process function calls; in production, each downstream
  service exposes its own internal HTTP API. Add a comment to each stub handler noting
  the downstream service and table it will call (see architecture Section 10 Call Map).
- `POST /v1/patient/recommendations` is the only HTTP-triggered write path into
  `llm_recommendations` — note this explicitly in the stub handler.
- Pydantic request/response models for all six endpoints should be defined as stubs in
  `services/patient-api/app/models.py` with all fields present but no validation logic.
- Port 8000 — this is the external-facing service and the primary entry point for testing.

---

## Group 3: Verification

### Step 12 — Smoke test: all services boot and report healthy

**What to do:**

- Run `docker-compose up --build`.
- Confirm each service container starts without error.
- Hit `GET /health` on each service and confirm `{"status": "ok"}` is returned.
- Confirm Postgres is reachable and `01-users.sql` + `02-tables.sql` ran successfully
  (check for table existence via `psql` or a DB client).
- Confirm NATS is reachable on port 4222 and the monitoring page is accessible on port 8222.

**Key files:**

```
docker-compose.yml
infra/postgres/init/01-users.sql
infra/postgres/init/02-tables.sql
```

**Notes and constraints:**

- No automated test suite is required at this stage — manual curl or a Makefile target is
  sufficient.
- A `Makefile` with `make up`, `make down`, and `make health` targets is recommended but optional.
- All seven `GET /health` responses must return HTTP 200 before this step is considered complete.
- Any NATS subscription errors or Postgres connection failures at startup must be resolved
  before proceeding to implementation steps.

---

## Reference: Service Port Map

| Service | Internal port | External port |
|---|---|---|
| Patient API | 8000 | 8000 |
| Ingestion Gateway | 8001 | 8001 |
| MPI | 8002 | 8002 |
| Reconciliation | 8003 | 8003 |
| Timeline | 8004 | 8004 |
| LLM Summary | 8005 | 8005 |
| Notification | 8006 | 8006 |
| Postgres | 5432 | 5432 |
| NATS client | 4222 | 4222 |
| NATS monitor | 8222 | 8222 |

## Reference: NATS Topic Ownership

| Topic | Producer | Consumer(s) |
|---|---|---|
| `raw.source-a` | Ingestion Gateway | MPI, Reconciliation |
| `raw.source-b` | Ingestion Gateway | MPI, Reconciliation |
| `raw.source-c` | Ingestion Gateway | MPI, Reconciliation |
| `reconciled.events` | Reconciliation | Timeline |
| `timeline.updated` | Timeline | LLM Summary |
| `risk.computed` | LLM Summary | Notification |
