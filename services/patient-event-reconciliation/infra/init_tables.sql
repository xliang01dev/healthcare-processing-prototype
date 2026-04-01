-- Durable event log: one row per incoming source event, append-only, never updated.
-- Exists because NATS core does not persist messages — if this service restarts or the
-- debounce window needs replaying, there is no way to re-read from the bus.
-- This table is the persistence layer that makes NATS core behave like a durable stream.
CREATE TABLE IF NOT EXISTS patient_event_reconciliation.event_logs (
    id                      BIGSERIAL PRIMARY KEY,
    canonical_patient_id    UUID   NOT NULL,
    source_system_id        BIGINT NOT NULL,
    message_id              TEXT   NOT NULL,
    event_type              TEXT   NOT NULL,
    payload                 JSONB  NOT NULL,
    source_system_occurred_at TIMESTAMPTZ NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Fast lookup for idempotency check (is message_id already processed?)
CREATE INDEX IF NOT EXISTS event_logs_message_id_idx
    ON patient_event_reconciliation.event_logs (message_id);

-- Fast lookup for range queries during reconciliation (fetch events for a patient by ID range)
CREATE INDEX IF NOT EXISTS event_logs_canonical_patient_idx
    ON patient_event_reconciliation.event_logs (canonical_patient_id);

-- Rolling audit table: one row per debounce window (active or historical).
-- Active windows have published_at IS NULL. Historical windows have published_at set.
-- Tracks the range of event_logs [first_event_log_id, last_event_log_id] that belong to each debounce window.
CREATE TABLE IF NOT EXISTS patient_event_reconciliation.pending_publish_debouncer (
    id                   BIGSERIAL   PRIMARY KEY,
    canonical_patient_id UUID        NOT NULL,
    first_event_log_id   BIGINT      NOT NULL REFERENCES patient_event_reconciliation.event_logs (id),
    last_event_log_id    BIGINT      NOT NULL REFERENCES patient_event_reconciliation.event_logs (id),
    scheduled_after      TIMESTAMPTZ NOT NULL,
    ceiling_at           TIMESTAMPTZ NOT NULL,
    published_at         TIMESTAMPTZ,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Partial index: only indexes unpublished rows (published_at IS NULL).
-- Keeps the index small as published rows are excluded — fast lookup for the active debounce window.
-- Fast lookup for active (unpublished) debounce windows only
CREATE INDEX IF NOT EXISTS pending_publish_debouncer_active_idx
    ON patient_event_reconciliation.pending_publish_debouncer (canonical_patient_id)
    WHERE published_at IS NULL;

-- Denormalized snapshot: one row per reconciliation, capturing current patient state across all systems
CREATE TABLE IF NOT EXISTS patient_event_reconciliation.resolved_events (
    id                      BIGSERIAL PRIMARY KEY,
    canonical_patient_id    UUID NOT NULL,
    event_log_ids           BIGINT[] NOT NULL,
    event_processing_start  TIMESTAMPTZ NOT NULL,
    event_processing_end    TIMESTAMPTZ NOT NULL,

    -- Demographics (normalized, can override golden_record)
    first_name              TEXT,
    last_name               TEXT,
    gender                  TEXT,  -- M or F

    -- Insurance & Coverage
    primary_plan            TEXT,
    member_id               TEXT,
    eligibility_status      TEXT,
    network_status          TEXT,
    authorization_required  BOOLEAN,
    authorization_status    TEXT,

    -- Current Encounter
    admission_date          TIMESTAMPTZ,
    discharge_date          TIMESTAMPTZ,
    facility_name           TEXT,
    attending_physician     TEXT,
    encounter_status        TEXT,

    -- Clinical - searchable text arrays
    diagnosis_codes         TEXT[],
    active_diagnoses        TEXT[],
    procedures              TEXT[],
    medications             TEXT[],
    allergies               TEXT[],
    lab_results             TEXT[],
    care_team               TEXT[],
    scheduled_followups     TEXT[],
    quality_flags           TEXT[],

    -- Unstructured
    clinical_notes          TEXT,
    resolution_log          TEXT NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for querying by patient and time
CREATE INDEX IF NOT EXISTS resolved_events_patient_timeline_idx
    ON patient_event_reconciliation.resolved_events (canonical_patient_id, created_at DESC);

-- GIN indexes for searching text arrays
CREATE INDEX IF NOT EXISTS resolved_events_diagnoses_idx
    ON patient_event_reconciliation.resolved_events USING GIN(diagnosis_codes);
CREATE INDEX IF NOT EXISTS resolved_events_medications_idx
    ON patient_event_reconciliation.resolved_events USING GIN(medications);
CREATE INDEX IF NOT EXISTS resolved_events_allergies_idx
    ON patient_event_reconciliation.resolved_events USING GIN(allergies);
CREATE INDEX IF NOT EXISTS resolved_events_care_team_idx
    ON patient_event_reconciliation.resolved_events USING GIN(care_team);

CREATE TABLE IF NOT EXISTS patient_event_reconciliation.reconciliation_conflicts (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID     NOT NULL,
    source_system_ids    BIGINT[] NOT NULL,
    conflict_type        TEXT     NOT NULL,
    detail               JSONB    NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
