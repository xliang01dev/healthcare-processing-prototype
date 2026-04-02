-- Timeline events from reconciliation service
CREATE TABLE IF NOT EXISTS patient_timeline.timeline_events (
    id                      BIGSERIAL PRIMARY KEY,
    canonical_patient_id    UUID NOT NULL,

    -- Reconciliation metadata
    event_log_ids           INT[] NOT NULL,
    event_processing_start  TIMESTAMPTZ NOT NULL,
    event_processing_end    TIMESTAMPTZ NOT NULL,

    -- Demographics
    first_name              TEXT,
    last_name               TEXT,
    gender                  TEXT,

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

    -- Clinical (text arrays for search)
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
    resolution_log          TEXT,

    -- Metadata
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index on canonical_patient_id for timeline queries
CREATE INDEX IF NOT EXISTS idx_timeline_events_canonical_patient_id
    ON patient_timeline.timeline_events (canonical_patient_id, created_at DESC);

-- Materialized view: latest timeline event per patient (for fast O(1) lookup)
CREATE MATERIALIZED VIEW IF NOT EXISTS patient_timeline.patient_timeline AS
    SELECT DISTINCT ON (canonical_patient_id) *
    FROM patient_timeline.timeline_events
    ORDER BY canonical_patient_id, created_at DESC
WITH NO DATA;

-- Unique index on canonical_patient_id (one row per patient)
-- Required for REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS patient_timeline_canonical_patient_id_idx
    ON patient_timeline.patient_timeline (canonical_patient_id);

-- Transfer ownership so hs_writer can REFRESH without needing pg_maintain
ALTER MATERIALIZED VIEW patient_timeline.patient_timeline OWNER TO hs_writer;

-- Initialize the materialized view (non-concurrent)
-- Required: REFRESH MATERIALIZED VIEW CONCURRENTLY can only be used on an already-populated view
REFRESH MATERIALIZED VIEW patient_timeline.patient_timeline;
