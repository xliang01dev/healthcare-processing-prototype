# MPI Database Schema — Master Patient Index Tables

## Summary

This document defines the three Postgres tables that back the Master Patient Index (MPI) service.
The MPI resolves source-specific patient identifiers from Source A (Labs), Source B (Pharmacy), and Source C (Health System) into a single
`canonical_patient_id` (UUID) used by all downstream services. No downstream service ever sees
a source-local ID — only the canonical UUID.

## Design Notes — Corrections from Proposed Schema

### 1. Primary key types must be consistent

The proposed schema mixed `varchar` and `UUID` for primary and foreign keys across tables.
`canonical_patient_id` must be `UUID` — the atomic upsert uses `gen_random_uuid()` and all
downstream services treat it as a UUID. Source-local IDs are `TEXT`.

### 2. mpi_source_system — auto-incrementing primary key with separate name column

`mpi_source_system` has a `source_system_id SERIAL PRIMARY KEY` (auto-increments on each insert)
and a `name VARCHAR` column for the human-readable source name (e.g. `'source-a'`).
`mpi_source_identities` foreign-keys to `source_system_id` as `INT`.

### 3. mpi_patients.shared_identifier must be UNIQUE and explicitly nullable

The entire atomic upsert pattern (`INSERT ... ON CONFLICT (shared_identifier) DO NOTHING`) depends
on a unique constraint on this column. Without it the conflict target is invalid and the race
condition is not prevented.

The column is nullable because Source C (EHR) may not include an MBI. A patient can be registered
without one and the MBI backfilled later. The unique constraint applies only to non-null values
(`NULLS NOT DISTINCT` is Postgres 15+; on earlier versions, null values are not compared so
multiple nulls are permitted by default — which is the desired behavior here).

### 4. source_patient_id was missing from mpi_source_identities

This is the ID the source system assigned to this patient (e.g. `"A-00492"`, `"SRC-B-9921"`).
Without it, the table holds demographic attributes but cannot answer the core MPI question:
"Source A just sent patient ID X — what is the canonical ID?" The lookup key for every incoming
raw event is `(source_system, source_patient_id)`.

### 5. Surrogate primary key on mpi_source_identities

Added a `BIGSERIAL` surrogate PK. The unique constraint on `(source_system, source_patient_id)`
enforces identity; the surrogate PK gives a stable row handle for any future FK references.

### 6. modified_at update responsibility

`modified_at` is present on both `mpi_patients` and `mpi_source_identities`. Postgres does not
update this automatically. A trigger or application-layer update is required. The column definition
sets a default of `NOW()` for the insert case; the application must set it explicitly on updates.
A trigger is the safer long-term choice.

### 7. Indexes

Three indexes are required:

- `mpi_patients(shared_identifier)` — covered by the UNIQUE constraint; no separate index needed.
- `mpi_source_identities(source_system_id, source_patient_id)` — covered by the UNIQUE constraint.
- `mpi_source_identities(last_name, date_of_birth)` — needed for the fallback name+DOB lookup
  when `shared_identifier` is absent.
- `mpi_source_identities(canonical_patient_id)` — needed to resolve all source identities for a
  given patient (the reverse lookup: UUID → all source rows).

---

## Table Descriptions

### mpi_source_system

A small reference table. One row per data source. `source_system_id` (SERIAL — auto-incrementing integer) is the primary key;
`name` (VARCHAR) holds the human-readable source name. `mpi_source_identities` foreign-keys to
`source_system_id` as INT. This table is seeded at startup with the three known sources and does not
change at runtime.

### mpi_patients

One row per unique real-world patient. Holds the canonical UUID and the shared cross-source
identifier (MBI). This is the table targeted by the atomic upsert — the unique constraint on
`shared_identifier` is the conflict target that prevents duplicate canonical IDs under parallel
inserts.

### mpi_source_identities

One row per (source, source_patient_id) pair seen by the MPI. Stores the demographics reported by
that source for this patient. The foreign key to `mpi_patients` resolves the canonical UUID. The
foreign key to `mpi_source_system` records which source sent this identity. All downstream services
resolve incoming events through this table.

---

## Corrected CREATE TABLE SQL

```sql
-- ============================================================
-- mpi_source_system
-- Reference table: one row per data source.
-- Seeded at startup; not written to during normal ingestion.
-- ============================================================
CREATE TABLE mpi_source_system (
    source_system_id  SERIAL       PRIMARY KEY,
    name              VARCHAR      NOT NULL UNIQUE  -- 'source-a' | 'source-b' | 'source-c'
);

-- Seed values (run once at startup)
INSERT INTO mpi_source_system (name) VALUES
    ('source-a'),   -- Labs / LIS
    ('source-b'),   -- Pharmacy / NCPDP
    ('source-c')    -- Health System / EHR
ON CONFLICT DO NOTHING;


-- ============================================================
-- mpi_patients
-- One row per unique real-world patient.
-- The atomic upsert targets the UNIQUE constraint on
-- shared_identifier to prevent duplicate canonical IDs.
-- ============================================================
CREATE TABLE mpi_patients (
    canonical_patient_id  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    shared_identifier     TEXT         UNIQUE,          -- MBI; nullable (may be absent from Source C / Health System)
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    modified_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Index on shared_identifier is already created by the UNIQUE constraint above.
-- No additional index needed for the atomic upsert conflict target.


-- ============================================================
-- mpi_source_identities
-- One row per (source, source_patient_id) pair.
-- This is the lookup table for all incoming raw events.
-- ============================================================
CREATE TABLE mpi_source_identities (
    id                    BIGSERIAL    PRIMARY KEY,
    canonical_patient_id  UUID         NOT NULL REFERENCES mpi_patients(canonical_patient_id),
    source_system_id      INT          NOT NULL REFERENCES mpi_source_system(source_system_id),
    source_patient_id     TEXT         NOT NULL,         -- the ID the source system assigned to this patient
    first_name            TEXT,
    last_name             TEXT,
    date_of_birth         DATE,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    modified_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (source_system_id, source_patient_id)         -- one canonical ID per source record, enforced
);

-- Lookup by incoming source event: "Source A sent patient ID X — what is the canonical UUID?"
-- Covered by the UNIQUE constraint above; no separate index needed.

-- Fallback lookup: name + DOB when shared_identifier is absent
CREATE INDEX idx_mpi_name_dob
    ON mpi_source_identities (last_name, date_of_birth);

-- Reverse lookup: all source identities for a given canonical patient
CREATE INDEX idx_mpi_canonical_patient
    ON mpi_source_identities (canonical_patient_id);
```

---

## Timeline — Materialized View

The patient timeline is a Postgres materialized view over `reconciliation_events`. The Timeline
Service does not write rows — it calls `REFRESH MATERIALIZED VIEW CONCURRENTLY patient_timeline`
when triggered by `reconciled.events`. Postgres recomputes the view from the event log.

```sql
-- ============================================================
-- patient_timeline
-- Materialized view: one row per patient, events as JSON array
-- ordered chronologically. Refreshed by Timeline Service on
-- each reconciled.events message.
--
-- CONCURRENTLY requires a unique index — reads are non-blocking
-- during refresh (reads continue against the prior snapshot).
-- ============================================================
CREATE MATERIALIZED VIEW patient_timeline AS
SELECT
    canonical_patient_id,
    json_agg(
        json_build_object(
            'event_type',     event_type,
            'event_date',     event_date,
            'version',        version,
            'source_system_id', source_system_id,
            'payload',        payload,
            'ingested_at',    ingested_at
        ) ORDER BY event_date ASC
    ) AS events
FROM  reconciliation_events
WHERE status = 'active'
GROUP BY canonical_patient_id;

-- Required for REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX idx_patient_timeline_pk
    ON patient_timeline (canonical_patient_id);
```

**Note:** `REFRESH` recomputes the entire view, not per-patient. This is a property of Postgres
materialized views — they cannot be `PARTITION BY`-declared, so the refresh always rebuilds the
full result set even though the underlying `reconciliation_events` table is hash-partitioned by
`canonical_patient_id`. Partition pruning helps the scan, but the view output is still replaced
whole. Per-patient incremental refresh (`pg_ivm`) is the production mitigation. For
`llm_pending_assessments` (a regular partitioned table), partitioning by `canonical_patient_id`
means each upsert hits exactly one partition — the only meaningful concern there is an uneven
patient distribution causing a hot partition.

---

## Reconciliation Tables

Three tables back the Reconciliation Service. They live in a separate schema from MPI but
foreign-key to `mpi_patients` for patient identity.

**Sharding:** when the Reconciliation Service scales horizontally, each instance owns its own
partition of all three tables, sharded by `canonical_patient_id` hash. Consistent hashing on
`canonical_patient_id` at the bus level ensures all events for a given patient always route to
the same instance — which writes only to its own partition. Instances never share these tables,
eliminating cross-instance write contention and idempotency race conditions.

```sql
-- ============================================================
-- reconciliation_events
-- Core event log. One row per accepted, versioned event.
-- R-F4 (correction), R-F5 (enrich), R-F6 (void) all write here.
-- ============================================================
CREATE TABLE reconciliation_events (
    id                    BIGSERIAL    PRIMARY KEY,
    canonical_patient_id  UUID         NOT NULL REFERENCES mpi_patients(canonical_patient_id),
    source_system_id      INT          NOT NULL REFERENCES mpi_source_system(source_system_id),
    source_record_id      TEXT         NOT NULL,   -- the source's own ID for this event
    upstream_event_id     TEXT,                    -- stable event ID assigned by the upstream source (optional)
                                                   -- if provided, used as the primary dedup key instead of
                                                   -- (canonical_patient_id, event_type, event_date) fuzzy match
    event_type            TEXT         NOT NULL,   -- 'lab_result' | 'medication_dispensed' | 'procedure'
    event_date            DATE         NOT NULL,
    version               INT          NOT NULL DEFAULT 1,
    status                TEXT         NOT NULL,   -- 'active' | 'superseded' | 'voided' | 'duplicate_suppressed'
    payload               JSONB        NOT NULL,   -- full event data
    ingested_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
    -- message_id is not stored here; it is sha256(source_system_id + source_record_id + version)
    -- and is computed by the server on demand
);

-- Patient lookup
CREATE INDEX idx_rec_events_patient
    ON reconciliation_events (canonical_patient_id);

-- Source lookup (versioning and correction path)
CREATE INDEX idx_rec_events_source
    ON reconciliation_events (source_system_id, source_record_id);

-- Chronological timeline lookup
CREATE INDEX idx_rec_events_event_date
    ON reconciliation_events (canonical_patient_id, event_date);

-- Cross-source dedup index (R-F1, R-F2)
-- Composite on (canonical_patient_id, event_type, upstream_event_id).
--
-- When upstream_event_id is present: UNIQUE enforces no duplicate (patient, type, event_id)
-- combinations — dedup resolves as a point lookup, no fuzzy matching needed.
--
-- When upstream_event_id is NULL: Postgres treats NULLs as not equal, so multiple rows
-- with the same (canonical_patient_id, event_type) and NULL upstream_event_id are permitted.
-- Application logic applies fuzzy event_date window matching for those rows.
CREATE UNIQUE INDEX idx_rec_events_dedup
    ON reconciliation_events (canonical_patient_id, event_type, upstream_event_id)
    WHERE status = 'active';


-- ============================================================
-- reconciliation_processed_messages
-- Idempotency table (R-F3). Checked before any other logic.
-- ============================================================
CREATE TABLE reconciliation_processed_messages (
    message_id    TEXT         PRIMARY KEY,
    processed_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    result_ref    BIGINT       REFERENCES reconciliation_events(id)  -- null for dropped/voided messages
);


-- ============================================================
-- reconciliation_conflicts
-- Holds events flagged by R-F2 (conflicting cross-source values)
-- and R-F7 (cross-source void) pending manual review.
-- ============================================================
CREATE TABLE reconciliation_conflicts (
    id                    BIGSERIAL    PRIMARY KEY,
    canonical_patient_id  UUID         NOT NULL REFERENCES mpi_patients(canonical_patient_id),
    conflict_type         TEXT         NOT NULL,   -- 'cross_source_value' | 'cross_source_void'
    field_name            TEXT,                    -- which field conflicted (null for whole-record void conflicts)
    message_id_a          TEXT         NOT NULL,
    message_id_b          TEXT         NOT NULL,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    resolved_at           TIMESTAMPTZ,
    resolution            TEXT                     -- outcome once manually adjudicated
);
```

---

## LLM Tables

Two tables back the LLM Summary Service debounce pattern and recommendation output.

```sql
-- ============================================================
-- llm_pending_assessments
-- Debounce table. Timeline Service upserts one row per patient
-- on each reconciled.events message, bumping scheduled_after
-- forward. LLM worker polls for rows where scheduled_after <
-- NOW() — meaning the patient has been quiet for the debounce
-- window and is ready for assessment.
--
-- Partitioned by HASH(canonical_patient_id) to distribute
-- upsert load across partitions and reduce per-partition
-- lock contention during burst ingestion.
-- ============================================================
CREATE TABLE llm_pending_assessments (
    canonical_patient_id  UUID         NOT NULL REFERENCES mpi_patients(canonical_patient_id),
    scheduled_after       TIMESTAMPTZ  NOT NULL,   -- bumped forward on each new event; LLM runs when this is in the past
    status                TEXT         NOT NULL DEFAULT 'pending',  -- 'pending' | 'processing' | 'done' | 'failed'
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (canonical_patient_id)
) PARTITION BY HASH (canonical_patient_id);

-- Partitions — modulus matches expected number of Timeline Service instances
CREATE TABLE llm_pending_assessments_p0 PARTITION OF llm_pending_assessments
    FOR VALUES WITH (modulus 4, remainder 0);
CREATE TABLE llm_pending_assessments_p1 PARTITION OF llm_pending_assessments
    FOR VALUES WITH (modulus 4, remainder 1);
CREATE TABLE llm_pending_assessments_p2 PARTITION OF llm_pending_assessments
    FOR VALUES WITH (modulus 4, remainder 2);
CREATE TABLE llm_pending_assessments_p3 PARTITION OF llm_pending_assessments
    FOR VALUES WITH (modulus 4, remainder 3);

CREATE INDEX idx_llm_pending_scheduled ON llm_pending_assessments (scheduled_after)
    WHERE status = 'pending';


-- ============================================================
-- llm_recommendations
-- Immutable output table. One row per completed assessment.
-- New assessments append a new row; prior rows are not updated.
-- Read surface for any future UI or API layer.
-- ============================================================
CREATE TABLE llm_recommendations (
    id                    BIGSERIAL    PRIMARY KEY,
    canonical_patient_id  UUID         NOT NULL REFERENCES mpi_patients(canonical_patient_id),
    risk_tier             TEXT         NOT NULL,   -- 'Low' | 'Medium' | 'High' | 'Critical'
    key_risks             JSONB        NOT NULL,   -- array of risk factor strings
    recommended_actions   JSONB        NOT NULL,   -- array of recommended care action strings
    summary               TEXT         NOT NULL,   -- plain-language summary
    prompt_version        TEXT         NOT NULL,
    model                 TEXT         NOT NULL,   -- backend identifier (e.g. 'dict-v1', 'ollama-llama3', 'claude-sonnet-4-6')
    mode                  TEXT         NOT NULL,   -- 'batch' | 'agent'
    content_hash          TEXT         NOT NULL,   -- SHA-256 of full output; used for deduplication before write
    has_changed_from_last BOOLEAN      NOT NULL,   -- false if structurally similar to prior row; true if materially different
    similarity_score      FLOAT,                   -- cosine similarity vs prior recommendation (null if not computed)
    generated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Dedup logic:
--   hash match                          → has_changed_from_last=false, similarity_score=null, skip write
--   hash differs + structural change    → has_changed_from_last=true,  similarity_score=null, write
--   hash differs + no structural change → has_changed_from_last=false, similarity_score=<computed>, tiebreaker write decision
-- Cosine similarity is only computed in the borderline case (hash changed, structure unchanged).

CREATE INDEX idx_llm_rec_patient ON llm_recommendations (canonical_patient_id, generated_at DESC);
```

---

## Relationship Diagram

```
mpi_source_system
    source_system_id (SERIAL, PK)
    name             (VARCHAR, UNIQUE)
         |
         | 1
         |
         * (many)
mpi_source_identities
    id                   (BIGSERIAL, PK)
    canonical_patient_id (UUID, FK → mpi_patients)
    source_system_id     (INT, FK → mpi_source_system)        ← SERIAL auto-increment
    source_patient_id    (TEXT)
    first_name           (TEXT)
    last_name            (TEXT)
    date_of_birth        (DATE)
    created_at           (TIMESTAMPTZ)
    modified_at          (TIMESTAMPTZ)
         |
         * (many)
         |
         | 1
mpi_patients
    canonical_patient_id (UUID, PK)
    shared_identifier    (TEXT, UNIQUE, nullable)
    created_at           (TIMESTAMPTZ)
    modified_at          (TIMESTAMPTZ)
```

---

## Atomic Upsert Pattern (for reference)

The MPI service uses this pattern for every incoming patient registration. It is safe under
concurrent inserts from all three sources arriving simultaneously.

```sql
-- Step 1: attempt insert; conflict on shared_identifier means patient already exists
INSERT INTO mpi_patients (shared_identifier)
VALUES ($mbi)
ON CONFLICT (shared_identifier) DO NOTHING;

-- Step 2: always select — returns the existing row if conflict occurred
SELECT canonical_patient_id
FROM   mpi_patients
WHERE  shared_identifier = $mbi;
```

When `shared_identifier` is null (Source C / Health System, no MBI), the application generates a UUID directly and
inserts without a conflict target. The fallback match against `last_name + date_of_birth` in
`mpi_source_identities` is attempted first; if a match is found the existing `canonical_patient_id`
is used. If no match is found, a new canonical patient is created.
```
