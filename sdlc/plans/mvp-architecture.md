# Healthcare Processing System - Architecture

## Overview

A microservices-based healthcare data processing system that ingests patient data from multiple sources (Medicare, Hospital EHR, Labs), performs identity resolution and reconciliation, and provides a unified patient view.

## Core Services

| Service | Responsibility |
|---------|-----------------|
| **Ingestion Gateway** | Parse raw events from sources (Medicare, Hospital, Labs). Assign `message-id` for idempotency. Publish to `raw.*` topics. |
| **Patient Data Service** | Resolve patient identity atomically across sources via shared anchor. Maintain golden record (merged demographics). Publish to `reconcile.{canonical_patient_id}`. |
| **Patient Event Reconciliation** | Consume `reconcile.*` events. Enforce idempotency via `event_logs`. Manage 5-second debounce window. Apply reconciliation rules. Publish `reconciled.events`. |
| **Patient Timeline** | Consume `reconciled.events`. Refresh materialized view (latest per patient). Publish `timeline.updated` after refresh. |
| **Patient Summary** | Consume `timeline.updated`. Fetch timeline + golden record. Run LLM risk assessment. Publish `risk.computed`. Nightly batch cron job. |
| **Patient API** | Public API gateway. Delegates to downstream services. |
| **NPI Registry** | Reference service for provider lookup. Query by NPI code → provider name, title, specialty. No message bus. |
| **Notification** | Consume `risk.computed`. Route alerts for High/Critical risk patients. |

## Service Summaries

**Ingestion Gateway** — The write entry point. Clients submit raw events (POST/PUT) representing patient data from external sources (Medicare, Hospital EHR, Labs). Parses submissions into internal JSON format, generates a stable `message-id` for idempotency, and publishes to the NATS bus. No business logic, only transformation and routing.

**Patient Data Service** — The master identity resolver. Answers: "Is this patient the same person I've seen before?" Uses a shared anchor (e.g., Medicare ID) to atomically upsert patient identities across sources. Maintains the golden record — a merged view of normalized demographics. Routes resolved events downstream via per-patient NATS subjects to ensure ordering.

**Patient Event Reconciliation** — The reconciliation engine. Receives staged events and accumulates them in an append-only event log. Implements a 5-second debounce window per patient (with a 30-minute ceiling) so batched events are reconciled together. When the window expires, applies business rules to merge conflicting data across sources and publishes the final reconciled snapshot.

**Patient Timeline** — The materialized view layer. Consumes reconciled events and stores the latest state per patient. Maintains a single-row-per-patient materialized view for ultra-fast O(1) lookups. Critically, refreshes the view before publishing the `timeline.updated` event (refresh-then-publish rule) to guarantee consistency.

**Patient Summary** — The AI layer. Triggered by timeline updates (event-driven) or runs nightly (batch). Fetches the patient's reconciled timeline and golden record, builds a prompt, and calls the LLM for risk assessment and recommended actions. Deduplicates results and publishes risk scores downstream.

**Patient API** — The read entry point. Exposes HTTP GET endpoints for external clients to retrieve patient data. Delegates to Patient Data Service (for golden record), Patient Timeline (for longitudinal history), and Patient Event Reconciliation (for conflict records). Stateless orchestration layer.

**NPI Registry** — A lightweight reference service for provider enrichment. Stores provider master data (names, credentials, specialties) indexed by National Provider Identifier (NPI code). No message bus coupling — purely synchronous lookup. Enables inline enrichment of provider references in reconciliation and risk assessment.

**Notification Service** — The alert dispatcher. Consumes risk assessment results and routes notifications for high/critical risk patients. Abstracts alert destination (console log, webhook, email, SMS) so the messaging layer can evolve independently.

## Message Bus Topics

| Topic | Producer | Consumer | Purpose |
|-------|----------|----------|---------|
| `raw.source-a/b/c` | Ingestion Gateway | Patient Data | Raw events from source systems |
| `patient.hydrate` | Internal | Patient Data | On-demand patient record hydration |
| `reconcile.{id}` | Patient Data | Patient Event Reconciliation | Stage events for reconciliation (per-patient ordering) |
| `reconciled.events` | Patient Event Reconciliation | Patient Timeline | Reconciled snapshot ready for timeline update |
| `timeline.updated` | Patient Timeline | Patient Summary | Trigger risk assessment for this patient |
| `risk.computed` | Patient Summary | Notification | Risk assessment result — route alerts |

## Data Flow

```mermaid
graph TD
    CLIENT["Clients<br/>(External Systems)"]
    
    CLIENT -->|POST /ingest| IG["Ingestion Gateway"]
    IG -->|assign message-id| IG
    IG -->|publish raw.source-*| BUS["NATS Bus"]
    
    BUS -->|raw.source-*| PD["Patient Data Service"]
    PD -->|resolve identity<br/>atomic upsert| PD
    PD -->|build golden record| PD
    PD -->|publish reconcile.id| BUS
    
    BUS -->|reconcile.*| RE["Reconciliation Service"]
    RE -->|idempotency check<br/>event_logs.message_id| RE
    RE -->|append to event_logs| RE
    RE -->|debounce 5s| RE
    RE -->|apply rules| RE
    RE -->|publish reconciled.events| BUS
    
    BUS -->|reconciled.events| TL["Timeline Service"]
    TL -->|insert into timeline_events| TL
    TL -->|REFRESH MATERIALIZED VIEW| TL
    TL -->|publish timeline.updated| BUS
    
    BUS -->|timeline.updated| PS["Patient Summary Service"]
    PS -->|GET /internal/patient/timeline| TL
    PS -->|GET /internal/patient/golden-record| PD
    PS -->|LLM risk assessment| PS
    PS -->|publish risk.computed| BUS
    
    BUS -->|risk.computed| NS["Notification Service"]
    NS -->|route alerts| NS
    
    API["Patient API"]
    CLIENT -->|GET /patient/{id}| API
    API -->|query| PD
    API -->|query| RE
    API -->|query| TL
    
    NPI["NPI Registry"]
    PS -->|GET /v1/npi/{code}| NPI
    RE -->|GET /v1/npi/{code}| NPI
```

## Key Patterns

### Identity Resolution (Race-Condition Safe)
- **Problem**: Three sources publish simultaneously with different patient IDs. Whichever arrives first "wins".
- **Solution**: Atomic `INSERT ... ON CONFLICT (shared_anchor) DO NOTHING` followed by `SELECT`.
  - First event creates the canonical UUID
  - Later events for same patient match to existing UUID
  - Order doesn't matter — correctness is guaranteed
- **Shared Anchor**: Registration ID agreed across all sources (equivalent to Medicare Beneficiary ID)

### Debouncing (Reconciliation Service Owned)
- **Why**: Multiple events from same source batch should be reconciled together, not individually
- **How**: 5-second debounce window per patient with hard deadline (30 minutes max)
  - New event within window: extend timer, update `last_event_log_id`
  - Timer expires: reconcile all events in range `[first_event_log_id, last_event_log_id]`
  - Exceeds ceiling: close window, start new one
- **Source of Truth**: Append-only `event_logs` table (NATS has no persistence)

### Idempotency
- Every inbound event gets `message_id = SHA256(source_id + version + source_system)`
- Reconciliation Service checks `event_logs.message_id` before processing
- Prevents re-processing of duplicates or retried events

### Materialized View (Timeline)
- Stores **only latest per patient** using `DISTINCT ON (canonical_patient_id)`
- Enables O(1) lookup: `SELECT * FROM patient_timeline WHERE canonical_patient_id = $1`
- Refreshed concurrently after each reconciliation
- **Critical**: Refresh must complete **before** publishing `timeline.updated` (refresh-then-publish rule)

### LLM Risk Assessment (Post-Reconciliation)
- Triggered by `timeline.updated` (event-driven) or nightly cron (batch)
- Always operates on latest, cleanest reconciled state
- No separate rule engine — LLM generates risk tier + recommendations
- Results deduped: hash → structural diff → cosine similarity

### Connection Pooling
- Each service manages its own asyncpg pool: `min_size=2, max_size=5`
- Total: ~5 services × 2 pools × 5 max = ~50 connections (under 150 limit)
- Pool sizes configurable via env vars `POSTGRES_POOL_MIN_SIZE` / `POSTGRES_POOL_MAX_SIZE`

### Module-Level Instantiation
- Services and data providers created at **module import time** (not in lifespan)
- Lifespan only handles `connect()` / `disconnect()` for resources
- Teardown order critical: `drain → remove_singleton → disconnect`

## Technology Stack

- **Message Bus**: NATS core (pub/sub only, no persistence — mitigated by `event_logs`)
- **Database**: PostgreSQL 16 with per-service schemas
- **ORM**: asyncpg (async Python driver, no ORM)
- **Framework**: FastAPI + async/await throughout
- **Container**: Docker Compose (dev) — one service per container
- **Package Management**: uv + pyproject.toml (monorepo)

## Event Processing Style

**Kappa Architecture**: Everything is a stream. Derived views (timeline, risk) are materialized from stream events. No separate batch ETL — only event-driven processing + optional nightly cron for backfill/safety.

## Data Models (Conceptual)

### Event Flow
```
Source Event → Ingestion → Event Log → Debounce → Reconcile → Resolved Event → Timeline → LLM Assessment → Alert
     ↓              ↓            ↓         ↓          ↓           ↓             ↓          ↓                 ↓
  Raw format   message-id   Idempotency  5s window  Rules    Snapshot    Latest per   Risk tier      High/Critical
              assignment    check        expiry              versioning  patient       generation     notification
```

### Key Entities
- **Canonical Patient ID**: UUID that ties all source identities for one real-world patient
- **Golden Record**: Merged, normalized demographics across all sources
- **Event Log**: Durable, append-only record (NATS persistence substitute)
- **Reconciled Event**: Denormalized snapshot capturing complete patient state at one point in time
- **Timeline**: Materialized view (one row per patient) for fast `GET /timeline/{patient_id}` queries
- **Risk Assessment**: LLM-generated stratification with recommended actions (auditability: model version + prompt version)

## Design Tradeoffs (MVP)

| Tradeoff | Choice | Rationale |
|----------|--------|-----------|
| **Message Persistence** | NATS core (no persistence) | Simpler setup; mitigated by `event_logs` audit table |
| **Horizontal Scaling** | Single instance per service | NATS core lacks consumer groups; use JetStream in production |
| **Patient Timeline View** | Refresh entire view, not per-patient | Acceptable for POC; per-patient refresh would need JetStream |
| **Data Standards** | Plain JSON, no shared schema | Flexibility for each service; coupling risk if contracts drift |
| **LLM Backend** | Mocked dictionary for POC | Fast iteration; swap in Anthropic API / Ollama / LangGraph later |
| **Single Postgres** | Per-service schemas, one DB instance | Sufficient for learning; production would use dedicated per-service DBs |
