# MVP Development Steps — Healthcare Data Processing Platform

## Summary

Execution plan for building the MVP from scratch. Steps are grouped by concern and ordered for
sequential execution. Steps 1–4 establish the project skeleton and infrastructure. Steps 5–11
create service stubs. Step 12 verifies all services boot and are healthy.

All services are FastAPI (Python 3.12+), managed with `uv` and `pyproject.toml` per service.
No ORM — `asyncpg` directly. No implementation logic in stubs — only structure, wiring, and
health checks.

## Assumptions

- Docker Compose is the only runtime for this phase.
- A single Postgres instance with per-service schemas is acceptable for the POC.
- NATS core (no JetStream) is sufficient — no message persistence.
- Python deps per service: `fastapi>=0.111`, `uvicorn[standard]>=0.29`, `nats-py>=2.7`,
  `asyncpg>=0.29`, `pydantic>=2.6`, `httpx>=0.27`.
- Dev extras per service: `pytest`, `pytest-asyncio`, `httpx`, `mypy`.
- Stub services must boot cleanly, connect to NATS and Postgres, and expose a `/health` endpoint.
  They must NOT implement business logic.

---

## Group 1: Project Skeleton and Infrastructure

### Step 1 — Create monorepo file structure with per-service directories and Dockerfiles

**What to create:**

- Monorepo root with a workspace-level `pyproject.toml`.
- One directory per service under `services/` — flat module layout (no `app/` subdirectory):
  - `services/ingestion-gateway/`
  - `services/patient-data/`
  - `services/patient-event-reconciliation/`
  - `services/patient-timeline/`
  - `services/patient-summary/`
  - `services/notification/`
  - `services/patient-api/`
- Inside each service directory:
  - `pyproject.toml` — project metadata and dependencies.
  - `Dockerfile` — multi-stage build: `uv sync` in build stage, `uvicorn main:app` in run stage.
  - `__init__.py` — empty.
  - `main.py` — FastAPI app with lifespan and `/health`.
- A top-level `schemas/` directory for internal JSON schema definitions (populated in later steps).
- A top-level `shared/` directory containing:
  - `message_bus.py` — stub
  - `singleton_store.py` — stub

**Key files:**

```
pyproject.toml                                  # workspace root
schemas/                                        # internal event schemas (placeholder)
shared/
  message_bus.py                                # stub
  singleton_store.py                            # stub
services/
  ingestion-gateway/
    pyproject.toml
    Dockerfile
    __init__.py
    main.py
    ingest_service.py
    ingest_router.py
  patient-data/
    pyproject.toml
    Dockerfile
    __init__.py
    main.py
    patient_data_service.py
    patient_data_provider.py
    internal_router.py
  patient-event-reconciliation/
    pyproject.toml
    Dockerfile
    __init__.py
    main.py
    patient_event_reconciliation_service.py
    patient_event_reconciliation_data_provider.py
    internal_router.py
  patient-timeline/
    pyproject.toml
    Dockerfile
    __init__.py
    main.py
    timeline_service.py
    timeline_data_provider.py
    internal_router.py
  patient-summary/
    pyproject.toml
    Dockerfile
    __init__.py
    main.py
    patient_summary_service.py
    patient_summary_data_provider.py
    agentic_handler.py
    internal_router.py
  notification/
    pyproject.toml
    Dockerfile
    __init__.py
    main.py
    notification_service.py
  patient-api/
    pyproject.toml
    Dockerfile
    __init__.py
    main.py
    patient_service_coordinator.py
    patients_router.py
    models.py
```

**Notes and constraints:**

- Each `Dockerfile` must use the same base image and `uv` invocation pattern for consistency.
- The workspace root `pyproject.toml` should declare `[tool.uv.workspace]` with `members`
  pointing to each service path.
- Service port assignments (set in Dockerfiles and compose): Patient API 8000, Ingestion Gateway
  8001, Patient Data 8002, Patient Event Reconciliation 8003, Patient Timeline 8004,
  Patient Summary 8005, Notification 8006.
- `main.py` in each service must define a `FastAPI` app with a `lifespan` context manager
  (stub — connections wired but no business logic) and a `GET /health` endpoint.
- Services and data providers are instantiated at **module level** (outside lifespan). Lifespan
  only calls `connect()` / `drain()` / `disconnect()`. All service references are stored in the
  singleton store (`shared/singleton_store.py`), not on `app.state`.

---

### Step 2 — Create `docker-compose.yml` for Postgres, NATS, and all services

**What to create:**

- `docker-compose.yml` at the repo root wiring together:
  - `postgres` — official `postgres:16` image, port 5432, volume for data persistence, env vars
    for `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`. Mounts
    `./infra/postgres/init/` as `/docker-entrypoint-initdb.d/` so SQL init files run automatically.
  - `nats` — official `nats:latest` image, port 4222 (client), port 8222 (monitoring).
  - All seven services — each built from its own `Dockerfile`, port-mapped per Step 1, with
    `depends_on: [postgres, nats]`, and environment variables for `NATS_URL`,
    `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_READER_USER`,
    `POSTGRES_READER_PASSWORD`, `POSTGRES_WRITER_USER`, `POSTGRES_WRITER_PASSWORD`.
  - Inter-service `*_URL` env vars for HTTP calls (Patient Summary and Patient API call downstream
    internal APIs — see Section 11 call map in architecture doc):
    - `PATIENT_DATA_URL` (used by patient-api, patient-summary)
    - `TIMELINE_URL` (used by patient-api, patient-summary)
    - `RECONCILIATION_URL` (used by patient-api)
    - `PATIENT_SUMMARY_URL` (used by patient-api)

**Key files:**

```
docker-compose.yml
infra/
  postgres/
    init/                              # SQL init files mounted here (populated in Steps 3–4)
```

**Notes and constraints:**

- Each service uses a **reader DSN** and **writer DSN** — separate Postgres users with scoped
  privileges (reader: `SELECT` only; writer: `SELECT`, `INSERT`, `UPDATE`, `DELETE`).
  Pass them as separate env vars (`POSTGRES_READER_USER`, `POSTGRES_WRITER_USER`, etc.).
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

- `hs_writer` role with `LOGIN`, password, and `CONNECT` on the database.
- `hs_reader` role with `LOGIN`, password, and `CONNECT` on the database.
- `GRANT` statements per service schema:
  - `hs_writer`: `SELECT`, `INSERT`, `UPDATE`, `DELETE` on all tables + `USAGE` on sequences.
  - `hs_reader`: `SELECT` only on all tables.
- `ALTER DEFAULT PRIVILEGES` so future tables in each schema automatically inherit the same grants.

**Key files:**

```
infra/postgres/init/01-users.sql
```

**Notes and constraints:**

- Schemas are created in `02-tables.sql` (Step 4). Grants reference schemas by name — execution
  order must be users before tables.
- `ALTER DEFAULT PRIVILEGES` is preferred over per-table grants.
- Schemas to grant on: `patient_data`, `patient_event_reconciliation`, `patient_timeline`,
  `patient_summary`.
- Ingestion Gateway, Notification, and Patient API have no DB schemas — no grants needed.

---

### Step 4 — Create `02-tables.sql` — all service schemas and tables

**What to create:**

- `infra/postgres/init/02-tables.sql`

**Contents to define (one schema block per service):**

- `CREATE SCHEMA IF NOT EXISTS` for each service that owns a DB:
  `patient_data`, `patient_event_reconciliation`, `patient_timeline`, `patient_summary`.

- **`patient_data` schema:**
  - `patient_data.patients` — `canonical_patient_id UUID PRIMARY KEY`, `shared_identifier TEXT UNIQUE`, `created_at`.
  - `patient_data.source_systems` — `id BIGSERIAL PRIMARY KEY`, `source_system_name TEXT UNIQUE`.
    Seed with `source-a`, `source-b`, `source-c` on creation.
  - `patient_data.source_identities` — `id BIGSERIAL PRIMARY KEY`, `canonical_patient_id UUID REFERENCES patients`, `source_system_id BIGINT REFERENCES source_systems`, `source_patient_id TEXT`, `first_name TEXT`, `last_name TEXT`, `date_of_birth DATE`, `created_at`.
    `UNIQUE (source_system_id, source_patient_id)`.
    Indexes: `(last_name, date_of_birth)` for fallback lookup; `(canonical_patient_id)` for reverse lookup.
  - `patient_data.golden_records` — `id BIGSERIAL PRIMARY KEY`, `canonical_patient_id UUID REFERENCES patients`, `first_name TEXT`, `last_name TEXT`, `date_of_birth DATE`, `source_system_ids BIGINT[]`, `updated_at TIMESTAMPTZ`, `created_at TIMESTAMPTZ`.

- **`patient_event_reconciliation` schema:**
  - `patient_event_reconciliation.event_logs` — `id BIGSERIAL PRIMARY KEY`, `canonical_patient_id UUID`, `source_system_id BIGINT`, `message_id TEXT`, `event_type TEXT`, `payload JSONB`, `occurred_at TIMESTAMPTZ`, `created_at TIMESTAMPTZ DEFAULT NOW()`.
    (Note: `source_system_id` and `canonical_patient_id` are plain values — no FK to other schemas.)
  - `patient_event_reconciliation.pending_publish` — `id BIGSERIAL PRIMARY KEY`, `canonical_patient_id UUID`, `last_event_log_id BIGINT REFERENCES event_logs(id)`, `scheduled_after TIMESTAMPTZ`, `ceiling_at TIMESTAMPTZ`, `published_at TIMESTAMPTZ`, `updated_at TIMESTAMPTZ DEFAULT NOW()`.
    Partial index: `(canonical_patient_id, last_event_log_id) WHERE published_at IS NULL`.
  - `patient_event_reconciliation.resolved_events` — `id BIGSERIAL PRIMARY KEY`, `canonical_patient_id UUID`, `source_system_ids BIGINT[]`, `from_event_log_id BIGINT REFERENCES event_logs(id)`, `to_event_log_id BIGINT REFERENCES event_logs(id)`, `payload JSONB`, `resolution_log TEXT`, `occurred_at TIMESTAMPTZ`, `created_at TIMESTAMPTZ DEFAULT NOW()`.
  - `patient_event_reconciliation.reconciliation_conflicts` — `id BIGSERIAL PRIMARY KEY`, `canonical_patient_id UUID`, `source_system_ids BIGINT[]`, `conflict_type TEXT`, `details JSONB`, `created_at TIMESTAMPTZ DEFAULT NOW()`.
  - `patient_event_reconciliation.processed_messages` — `message_id TEXT PRIMARY KEY`, `processed_at TIMESTAMPTZ DEFAULT NOW()`.

- **`patient_timeline` schema:**
  - `patient_timeline.timeline_events` — `id BIGSERIAL PRIMARY KEY`, `canonical_patient_id UUID`, `event_type TEXT`, `payload JSONB`, `occurred_at TIMESTAMPTZ`, `source_system_id BIGINT`, `created_at TIMESTAMPTZ DEFAULT NOW()`.
    (`source_system_id` is a plain value — cross-schema boundary; no FK.)
  - Materialized view `patient_timeline.patient_timeline` over `timeline_events`, ordered by `occurred_at` per patient.
  - Unique index on the materialized view required for `REFRESH MATERIALIZED VIEW CONCURRENTLY`.

- **`patient_summary` schema:**
  - `patient_summary.recommendations` — `id BIGSERIAL PRIMARY KEY`, `canonical_patient_id UUID`, `risk_tier TEXT`, `key_risks JSONB`, `recommended_actions JSONB`, `summary TEXT`, `model TEXT`, `prompt_version TEXT`, `mode TEXT`, `has_changed_from_last BOOLEAN`, `similarity_score FLOAT`, `generated_at TIMESTAMPTZ DEFAULT NOW()`.
    Index on `(canonical_patient_id, generated_at DESC)`.

- **Ingestion Gateway, Notification, Patient API** — no schemas or tables (stateless services).

**Key files:**

```
infra/postgres/init/02-tables.sql
```

**Notes and constraints:**

- `event_logs` must be created before `pending_publish` and `resolved_events` (FK target).
- Cross-schema FK references are **not used** — `source_system_id` in `event_logs` and
  `timeline_events` is a plain `BIGINT` value, not a FK to `patient_data.source_systems`. This
  preserves service boundary isolation (in production, schemas would be on separate DB instances).
- The materialized view unique index must be created immediately after the view definition.
- `REFRESH MATERIALIZED VIEW CONCURRENTLY` requires the unique index to exist at refresh time.

---

## Group 2: Service Stubs

All stubs in this group follow the same structure:

- Module-level instantiation of `MessageBus` and data providers (where applicable).
- Module-level `register_singleton(ServiceClass, ServiceClass(...))`.
- `FastAPI` app with a `lifespan` context manager that calls `connect()` on bus and data provider,
  subscribes to NATS topics with no-op handlers, calls `drain()` / `remove_singleton()` /
  `disconnect()` on shutdown — in that order.
- `GET /health` endpoint returning `{"status": "ok", "service": "<service-name>"}`.
- No business logic. No database writes beyond connection validation.
- All env vars (`NATS_URL`, `POSTGRES_*`, `*_URL`) read from environment.

---

### Step 5 — Ingestion Gateway stub

**What to create:**

- `services/ingestion-gateway/main.py` — FastAPI app. Module-level: `bus = MessageBus(...)`,
  `register_singleton(IngestService, IngestService(bus))`.
- `services/ingestion-gateway/ingest_service.py` — `IngestService` class with `bus: MessageBus`
  constructor param and a stub `ingest_event(source, body)` method.
- `services/ingestion-gateway/ingest_router.py` — stub router with three POST endpoints:
  - `POST /ingest/source-a`
  - `POST /ingest/source-b`
  - `POST /ingest/source-c`
  Each accepts a JSON body, calls `get_singleton(IngestService).ingest_event(...)`, returns
  `{"received": true}`.

**Key files:**

```
services/ingestion-gateway/main.py
services/ingestion-gateway/ingest_service.py
services/ingestion-gateway/ingest_router.py
```

**Notes and constraints:**

- Ingestion Gateway is stateless — no Postgres connection needed.
- `IngestService` receives `MessageBus` via constructor. It never accesses `app.state`.
- Lifespan: `await bus.connect()` → subscribe (no-op) → yield → `await bus.drain()` →
  `remove_singleton(IngestService)`.
- Topics this service will publish to (TODO comments only at stub stage):
  `raw.source-a`, `raw.source-b`, `raw.source-c`.
- The `message-id` derivation (`sha256(source_id + version + source_system)`) is not
  implemented — add a TODO comment in `ingest_event`.

---

### Step 6 — Patient Data Service stub

**What to create:**

- `services/patient-data/patient_data_provider.py` — `PatientDataProvider` class with reader/writer
  DSN constructor params and stub methods: `connect()`, `disconnect()`, `upsert_patient()`,
  `upsert_source_identity()`, `upsert_golden_record()`, `fetch_golden_record()`.
- `services/patient-data/patient_data_service.py` — `PatientDataService` class with
  `data_provider: PatientDataProvider` and `bus: MessageBus` constructor params.
  Stub methods: `handle_source_event(msg)`, `handle_hydrate(msg)`.
- `services/patient-data/internal_router.py` — stub internal router:
  - `GET /internal/patient/{canonical_patient_id}/golden-record` → `{"stub": true}`
- `services/patient-data/main.py` — module-level: `data_provider`, `bus`,
  `register_singleton(PatientDataService, PatientDataService(data_provider, bus))`.
  Lifespan subscribes to `raw.source-a`, `raw.source-b`, `raw.source-c`, `patient.hydrate`
  with no-op handlers.

**Key files:**

```
services/patient-data/main.py
services/patient-data/patient_data_service.py
services/patient-data/patient_data_provider.py
services/patient-data/internal_router.py
```

**Notes and constraints:**

- This service consumes raw topics and publishes to `reconcile.{canonical_patient_id}` — add
  TODO comments in `handle_source_event`.
- The atomic upsert pattern (`INSERT ... ON CONFLICT DO NOTHING; SELECT ...`) is the critical
  implementation detail — add a TODO comment in `upsert_patient` pointing to architecture Section 3.
- `canonical_patient_id` is embedded in the NATS subject (`reconcile.{id}`) — no synchronous
  HTTP call is made by Patient Event Reconciliation to resolve identity.
- Golden record is built/updated on every source identity upsert — add TODO in
  `upsert_golden_record`.
- Teardown order: `drain → remove_singleton → disconnect`.

---

### Step 7 — Patient Event Reconciliation stub

**What to create:**

- `services/patient-event-reconciliation/patient_event_reconciliation_data_provider.py` —
  `PatientEventReconciliationDataProvider` with reader/writer DSN params and stub methods:
  `connect()`, `disconnect()`, `is_message_processed(message_id)`, `mark_message_processed(message_id)`,
  `insert_event_log(...)`, `upsert_pending_publish(...)`, `insert_resolved_event(...)`,
  `fetch_conflicts(canonical_patient_id, page, page_size)`.
- `services/patient-event-reconciliation/patient_event_reconciliation_service.py` —
  `PatientEventReconciliationService` with `data_provider` and `bus: MessageBus` constructor params.
  Stub methods: `handle_reconcile_event(msg)`, `fetch_conflicts(...)`.
- `services/patient-event-reconciliation/internal_router.py` — stub:
  - `GET /internal/patient/{canonical_patient_id}/conflicts` → `[]`
- `services/patient-event-reconciliation/main.py` — module-level: `data_provider`, `bus`,
  `register_singleton(...)`. Lifespan subscribes to `reconcile.*` (wildcard).

**Key files:**

```
services/patient-event-reconciliation/main.py
services/patient-event-reconciliation/patient_event_reconciliation_service.py
services/patient-event-reconciliation/patient_event_reconciliation_data_provider.py
services/patient-event-reconciliation/internal_router.py
```

**Notes and constraints:**

- Subscribes to `reconcile.*` — wildcard captures all per-patient subjects
  (`reconcile.{canonical_patient_id}`). NATS guarantees per-subject ordering, which makes the
  debounce logic safe without cross-instance coordination.
- `canonical_patient_id` is extracted from `msg.subject` (e.g. `reconcile.abc-123` → `abc-123`)
  — no HTTP call to resolve identity. Add a TODO comment showing this extraction.
- Idempotency check via `processed_messages` — add TODO in `handle_reconcile_event`.
- Debounce logic (`event_logs` → `pending_publish`) — add TODO referencing architecture Section 5.
- Publishes to `reconciled.events` after debounce window expires — add TODO.

---

### Step 8 — Patient Timeline Service stub

**What to create:**

- `services/patient-timeline/timeline_data_provider.py` — `TimelineDataProvider` with reader/writer
  DSN params and stub methods: `connect()`, `disconnect()`, `refresh_patient_timeline()`,
  `fetch_patient_timeline(canonical_patient_id, page, page_size)`.
- `services/patient-timeline/timeline_service.py` — `TimelineService` with `data_provider` and
  `bus: MessageBus` constructor params. Stub methods: `handle_reconciled_event(msg)`,
  `fetch_patient_timeline(...)`.
- `services/patient-timeline/internal_router.py` — stub:
  - `GET /internal/patient/timeline?canonical_patient_id=&page=&page_size=` → `[]`
- `services/patient-timeline/main.py` — module-level: `data_provider`, `bus`,
  `register_singleton(TimelineService, ...)`. Lifespan subscribes to `reconciled.events`.

**Key files:**

```
services/patient-timeline/main.py
services/patient-timeline/timeline_service.py
services/patient-timeline/timeline_data_provider.py
services/patient-timeline/internal_router.py
```

**Notes and constraints:**

- Patient Timeline is a pure reactor — it does not own a debounce table. Debounce is in
  Patient Event Reconciliation. Timeline just refreshes the materialized view and publishes.
- The refresh-then-publish ordering rule is the critical constraint: `REFRESH MATERIALIZED VIEW
  CONCURRENTLY patient_timeline` must complete before `timeline.updated` is published.
  Add a TODO comment with this rule clearly stated in `handle_reconciled_event`.
- `REFRESH MATERIALIZED VIEW CONCURRENTLY` requires a unique index on the view — confirm the
  index exists in `02-tables.sql` (Step 4).
- Publishing `timeline.updated` is not implemented in the stub — add a TODO.

---

### Step 9 — Patient Summary Service stub

**What to create:**

- `services/patient-summary/patient_summary_data_provider.py` — `PatientSummaryDataProvider`
  with reader/writer DSN params and stub methods: `connect()`, `disconnect()`,
  `insert_recommendation(...)`, `fetch_latest_recommendation(...)`,
  `fetch_recommendations(...)`.
- `services/patient-summary/agentic_handler.py` — stub `AgenticHandler` class with abstract
  `complete(prompt: str, context: dict)` method. The demo implementation returns an empty result
  with simulated async delay.
- `services/patient-summary/patient_summary_service.py` — `PatientSummaryService` with
  `data_provider`, `http_client: httpx.AsyncClient`, `bus: MessageBus`,
  `timeline_url: str`, `patient_data_url: str` constructor params.
  Stub methods: `_fetch_patient_timeline(canonical_patient_id)`,
  `_fetch_golden_record(canonical_patient_id)`, `_assess_patient(canonical_patient_id)`,
  `handle_timeline_updated(msg)`, `run_batch_for_patient(canonical_patient_id)`, `run_batch()`.
- `services/patient-summary/internal_router.py` — stub:
  - `GET /internal/patient/{canonical_patient_id}/recommendation` → `None`
  - `GET /internal/patient/{canonical_patient_id}/recommendations` → `[]`
  - `POST /internal/patient/recommendations` → `{"queued": true}`
- `services/patient-summary/main.py` — module-level: `data_provider`, `http_client = httpx.AsyncClient()`,
  `bus`, `register_singleton(PatientSummaryService, PatientSummaryService(...))`.
  Lifespan: `connect()` bus and data provider, subscribe `timeline.updated`.
  Teardown: `drain → remove_singleton → http_client.aclose() → disconnect`.

**Key files:**

```
services/patient-summary/main.py
services/patient-summary/patient_summary_service.py
services/patient-summary/patient_summary_data_provider.py
services/patient-summary/agentic_handler.py
services/patient-summary/internal_router.py
```

**Notes and constraints:**

- `httpx.AsyncClient` is instantiated at module level (synchronous `__init__`). It is closed in
  lifespan teardown via `await http_client.aclose()` — after `remove_singleton` but before
  the data provider disconnects.
- `_fetch_patient_timeline` calls `GET {timeline_url}/internal/patient/timeline?canonical_patient_id={id}`.
- `_fetch_golden_record` calls `GET {patient_data_url}/internal/patient/{id}/golden-record`.
- `_assess_patient` is the shared logic called by both event-driven and batch paths — add TODOs
  for the full sequence (fetch timeline → fetch golden record → build prompt → call LLM →
  dedup check → insert recommendation → publish `risk.computed`).
- `run_batch()` is the cron entry point — add a TODO referencing architecture Section 6 batch steps.
- Deduplication write path (hash check → structural diff → cosine similarity) — add a TODO.
- `pyproject.toml` for this service needs `httpx` as a runtime dependency.

---

### Step 10 — Notification Service stub

**What to create:**

- `services/notification/notification_service.py` — `NotificationService` class with
  `bus: MessageBus` constructor param. Stub `handle_risk_computed(msg)` method that logs receipt.
- `services/notification/main.py` — module-level: `bus`, `register_singleton(NotificationService, ...)`.
  Lifespan subscribes to `risk.computed` with a no-op handler that calls
  `get_singleton(NotificationService).handle_risk_computed(msg)`.
  Teardown: `drain → remove_singleton`.

**Key files:**

```
services/notification/main.py
services/notification/notification_service.py
```

**Notes and constraints:**

- Notification Service has no database tables — stateless. No asyncpg pool needed.
- The alert routing logic (High/Critical risk tier → console log or webhook) is not implemented —
  add a TODO comment in `handle_risk_computed`.
- Add a `WEBHOOK_URL` env var placeholder in `docker-compose.yml` (empty by default).

---

### Step 11 — Patient API Service stub

**What to create:**

- `services/patient-api/patient_service_coordinator.py` — `PatientServiceCoordinator` class with
  `http_client: httpx.AsyncClient`, `patient_data_url: str`, `reconciliation_url: str`,
  `timeline_url: str`, `patient_summary_url: str` constructor params. Stub methods for each
  downstream call (add TODO comments pointing to the target internal endpoint per the architecture
  Section 11 call map).
- `services/patient-api/patients_router.py` — stub router with all six endpoints:
  - `GET /v1/patient/{canonical_patient_id}/info` → `{"stub": true}`
  - `GET /v1/patient/{canonical_patient_id}/timelines` → `{"stub": true}`
  - `GET /v1/patient/{canonical_patient_id}/recommendation` → `{"stub": true}`
  - `GET /v1/patient/{canonical_patient_id}/recommendations` → `{"stub": true}`
  - `GET /v1/patient/{canonical_patient_id}/conflicts` → `{"stub": true}`
  - `POST /v1/patient/recommendations` → `{"stub": true}`
- `services/patient-api/models.py` — Pydantic stub models for request/response shapes.
- `services/patient-api/main.py` — module-level: `http_client = httpx.AsyncClient()`,
  `register_singleton(PatientServiceCoordinator, PatientServiceCoordinator(http_client=..., ...))`.
  Lifespan: teardown calls `remove_singleton(PatientServiceCoordinator)`,
  `await http_client.aclose()`.

**Key files:**

```
services/patient-api/main.py
services/patient-api/patient_service_coordinator.py
services/patient-api/patients_router.py
services/patient-api/models.py
```

**Notes and constraints:**

- Patient API has no NATS connection and no Postgres pool — HTTP-only orchestration layer.
- `httpx.AsyncClient` is instantiated at module level. It is closed in lifespan teardown.
- `POST /v1/patient/recommendations` is the only HTTP-triggered path to trigger a single-patient
  assessment — note this explicitly in the stub handler.
- Port 8000 — the external-facing entry point for testing.

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
| Patient Data | 8002 | 8002 |
| Patient Event Reconciliation | 8003 | 8003 |
| Patient Timeline | 8004 | 8004 |
| Patient Summary | 8005 | 8005 |
| Notification | 8006 | 8006 |
| Postgres | 5432 | 5432 |
| NATS client | 4222 | 4222 |
| NATS monitor | 8222 | 8222 |

---

## Reference: NATS Topic Ownership

| Topic | Producer | Consumer(s) |
|---|---|---|
| `raw.source-a` | Ingestion Gateway | Patient Data Service |
| `raw.source-b` | Ingestion Gateway | Patient Data Service |
| `raw.source-c` | Ingestion Gateway | Patient Data Service |
| `patient.hydrate` | Internal | Patient Data Service |
| `reconcile.{canonical_patient_id}` | Patient Data Service | Patient Event Reconciliation |
| `reconciled.events` | Patient Event Reconciliation | Patient Timeline Service |
| `timeline.updated` | Patient Timeline Service | Patient Summary Service |
| `risk.computed` | Patient Summary Service | Notification Service |

---

## Reference: Inter-Service HTTP Calls

| Caller | Target service | Internal endpoint |
|---|---|---|
| Patient Summary | Patient Timeline | `GET /internal/patient/timeline?canonical_patient_id=` |
| Patient Summary | Patient Data | `GET /internal/patient/{id}/golden-record` |
| Patient API | Patient Data | `GET /internal/patient/{id}/golden-record` |
| Patient API | Patient Timeline | `GET /internal/patient/timeline` |
| Patient API | Patient Event Reconciliation | `GET /internal/patient/{id}/conflicts` |
| Patient API | Patient Summary | `GET /internal/patient/{id}/recommendation` |
| Patient API | Patient Summary | `GET /internal/patient/{id}/recommendations` |
| Patient API | Patient Summary | `POST /internal/patient/recommendations` |
