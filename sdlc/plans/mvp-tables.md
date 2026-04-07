# MVP Database Schema

This document describes the current MVP Postgres schema across all services.

---

## Patient Data Service (`patient_data` schema)

Stores patient identity resolution and golden record (merged demographics).

### patients
One row per unique real-world patient. `canonical_patient_id` (UUID) is the system-wide patient identifier.

```sql
CREATE TABLE IF NOT EXISTS patient_data.patients (
    canonical_patient_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shared_identifier     TEXT NOT NULL UNIQUE,      -- Medicare Beneficiary ID (shared anchor)
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### source_systems
Reference table: one row per data source (Medicare, Hospital, Labs). Seeded at startup.

```sql
CREATE TABLE IF NOT EXISTS patient_data.source_systems (
    source_system_id   BIGSERIAL PRIMARY KEY,
    source_system_name TEXT NOT NULL UNIQUE          -- 'Medicare' | 'Hospital' | 'Labs'
);
```

### source_identities
One row per (source, source_patient_id) pair. Maps source-local IDs to canonical patient.

```sql
CREATE TABLE IF NOT EXISTS patient_data.source_identities (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID   NOT NULL REFERENCES patient_data.patients (canonical_patient_id),
    source_system_id     BIGINT NOT NULL REFERENCES patient_data.source_systems (source_system_id),
    source_patient_id    TEXT   NOT NULL,            -- source's own patient ID
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_system_id, source_patient_id)
);
```

### golden_records
Merged, normalized demographics across all sources for each patient.

```sql
CREATE TABLE IF NOT EXISTS patient_data.golden_records (
    canonical_patient_id UUID        PRIMARY KEY REFERENCES patient_data.patients (canonical_patient_id),
    source_system_ids    BIGINT[]    NOT NULL,       -- array of contributing source IDs
    given_name           TEXT,
    family_name          TEXT,
    date_of_birth        DATE,
    gender               TEXT,
    record_version       BIGINT      NOT NULL DEFAULT 1,
    last_reconciled_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Patient Event Reconciliation Service (`patient_event_reconciliation` schema)

Handles debounce coordination and reconciliation rule application.

### event_logs
Append-only event log. One row per inbound source event. Provides durability (NATS core is fire-and-forget) and idempotency (message_id check).

```sql
CREATE TABLE IF NOT EXISTS patient_event_reconciliation.event_logs (
    id                      BIGSERIAL PRIMARY KEY,
    canonical_patient_id    UUID   NOT NULL,
    source_system_id        BIGINT NOT NULL,
    message_id              TEXT   NOT NULL,         -- SHA256(source_id + version + source_system)
    event_type              TEXT   NOT NULL,         -- e.g., "medicare_enrollment"
    payload                 JSONB  NOT NULL,         -- full event data from source
    source_system_occurred_at TIMESTAMPTZ NOT NULL,  -- when event happened in source system
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS event_logs_message_id_idx
    ON patient_event_reconciliation.event_logs (message_id);
CREATE INDEX IF NOT EXISTS event_logs_canonical_patient_idx
    ON patient_event_reconciliation.event_logs (canonical_patient_id);
```

### pending_publish_debouncer
Rolling audit table tracking debounce windows per patient. Active windows have `published_at IS NULL`.

```sql
CREATE TABLE IF NOT EXISTS patient_event_reconciliation.pending_publish_debouncer (
    id                   BIGSERIAL   PRIMARY KEY,
    canonical_patient_id UUID        NOT NULL,
    first_event_log_id   BIGINT      NOT NULL REFERENCES patient_event_reconciliation.event_logs (id),
    last_event_log_id    BIGINT      NOT NULL REFERENCES patient_event_reconciliation.event_logs (id),
    scheduled_after      TIMESTAMPTZ NOT NULL,      -- when debounce window expires (bumped forward on each event)
    ceiling_at           TIMESTAMPTZ NOT NULL,      -- hard deadline (30 minutes)
    published_at         TIMESTAMPTZ,               -- NULL if active, set when task published
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS pending_publish_debouncer_active_idx
    ON patient_event_reconciliation.pending_publish_debouncer (canonical_patient_id)
    WHERE published_at IS NULL;                      -- only index active windows
```

### resolved_events
Denormalized snapshot: one row per reconciliation, capturing complete patient state across all systems at a point in time.

```sql
CREATE TABLE IF NOT EXISTS patient_event_reconciliation.resolved_events (
    id                      BIGSERIAL PRIMARY KEY,
    canonical_patient_id    UUID NOT NULL,
    event_log_ids           BIGINT[] NOT NULL,      -- IDs of events reconciled in this window
    event_processing_start  TIMESTAMPTZ NOT NULL,   -- when debounce window opened
    event_processing_end    TIMESTAMPTZ NOT NULL,   -- when reconciliation completed
    first_name              TEXT,
    last_name               TEXT,
    gender                  TEXT,
    primary_plan            TEXT,
    member_id               TEXT,
    eligibility_status      TEXT,
    network_status          TEXT,
    authorization_required  BOOLEAN,
    authorization_status    TEXT,
    admission_date          TIMESTAMPTZ,
    discharge_date          TIMESTAMPTZ,
    facility_name           TEXT,
    attending_physician     TEXT,
    encounter_status        TEXT,
    diagnosis_codes         TEXT[],
    active_diagnoses        TEXT[],
    procedures              TEXT[],
    medications             TEXT[],
    allergies               TEXT[],
    lab_results             TEXT[],
    care_team               TEXT[],
    scheduled_followups     TEXT[],
    quality_flags           TEXT[],
    clinical_notes          TEXT,
    resolution_log          TEXT NOT NULL,          -- how conflicts were resolved
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS resolved_events_patient_timeline_idx
    ON patient_event_reconciliation.resolved_events (canonical_patient_id, created_at DESC);
CREATE INDEX IF NOT EXISTS resolved_events_diagnoses_idx
    ON patient_event_reconciliation.resolved_events USING GIN(diagnosis_codes);
CREATE INDEX IF NOT EXISTS resolved_events_medications_idx
    ON patient_event_reconciliation.resolved_events USING GIN(medications);
```

### reconciliation_conflicts
Tracks data conflicts detected during reconciliation (not yet exposed in MVP). Deferred to future enhancement.

```sql
CREATE TABLE IF NOT EXISTS patient_event_reconciliation.reconciliation_conflicts (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID     NOT NULL,
    source_system_ids    BIGINT[] NOT NULL,
    conflict_type        TEXT     NOT NULL,         -- conflict category
    detail               JSONB    NOT NULL,         -- conflict details
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Patient Timeline Service (`patient_timeline` schema)

Materialized view layer for fast O(1) patient lookups.

### timeline_events
One row per reconciliation event. Timeline Service inserts here after reconciliation completes.

```sql
CREATE TABLE IF NOT EXISTS patient_timeline.timeline_events (
    id                      BIGSERIAL PRIMARY KEY,
    canonical_patient_id    UUID NOT NULL,
    event_log_ids           INT[] NOT NULL,
    event_processing_start  TIMESTAMPTZ NOT NULL,
    event_processing_end    TIMESTAMPTZ NOT NULL,
    -- ... same denormalized fields as resolved_events ...
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_timeline_events_canonical_patient_id
    ON patient_timeline.timeline_events (canonical_patient_id, created_at DESC);
```

### patient_timeline (Materialized View)
Latest event per patient. Enables O(1) lookup: `SELECT * FROM patient_timeline WHERE canonical_patient_id = $1`.

Refreshed via `REFRESH MATERIALIZED VIEW CONCURRENTLY patient_timeline` by Timeline Service after each reconciliation (refresh-then-publish rule).

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS patient_timeline.patient_timeline AS
    SELECT DISTINCT ON (canonical_patient_id) *
    FROM patient_timeline.timeline_events
    ORDER BY canonical_patient_id, created_at DESC;

CREATE UNIQUE INDEX IF NOT EXISTS patient_timeline_canonical_patient_id_idx
    ON patient_timeline.patient_timeline (canonical_patient_id);  -- required for concurrent refresh
```

---

## Patient Summary Service (`patient_summary` schema)

LLM-generated risk assessments and recommendations.

### recommendations
One row per recommendation generated by LLM. Append-only (never updated). Content hash enables deduplication.

```sql
CREATE TABLE IF NOT EXISTS patient_summary.recommendations (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID NOT NULL,
    summary              TEXT NOT NULL,              -- LLM-generated recommendation text
    risk_tier            TEXT NOT NULL CHECK (      -- 'low' | 'medium' | 'high' | 'critical'
        risk_tier IN ('low', 'medium', 'high', 'critical')
    ),
    content_hash         TEXT NOT NULL,              -- SHA256(summary); used for deduplication
    generated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Key Design Patterns

### Identity Resolution (Race-Condition Safe)
Atomic upsert on `patients(shared_identifier)` via `INSERT ... ON CONFLICT ... DO NOTHING` ensures correctness under concurrent inserts from all sources.

### Debouncing (5-second Window)
Each event bumps `pending_publish_debouncer.scheduled_after` forward. When debounce expires, a reconciliation task is published to JetStream and `published_at` is set.

Serialized via Postgres row locks (`SELECT ... FOR UPDATE`) within `writer_transaction()` context.

### Idempotency
Event `message_id = SHA256(source_id + version + source_system)` is checked in `event_logs` before processing. Prevents re-processing duplicates.

### Materialized View (Timeline)
`REFRESH MATERIALIZED VIEW CONCURRENTLY` allows concurrent reads while refresh happens. Must complete **before** publishing `timeline.updated` event (refresh-then-publish rule).

### Recommendation Deduplication
Content hash (SHA256 of summary) enables duplicate detection. Full similarity matching (cosine) is deferred to future enhancement.

---

## Service Schemas

- `patient_data` — Patient identity, sources, golden record
- `patient_event_reconciliation` — Event log, debounce, reconciliation, conflicts
- `patient_timeline` — Timeline events and materialized view
- `patient_summary` — LLM recommendations

Each service has a dedicated schema for isolation and clarity.
