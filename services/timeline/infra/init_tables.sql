CREATE TABLE IF NOT EXISTS timeline.pending_processing (
    canonical_patient_id UUID PRIMARY KEY,
    scheduled_after      TIMESTAMPTZ NOT NULL,
    status               TEXT NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Source table backing the materialized view
CREATE TABLE IF NOT EXISTS timeline.timeline_events (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID NOT NULL,
    event_type           TEXT NOT NULL,
    payload              JSONB NOT NULL,
    event_time           TIMESTAMPTZ NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE MATERIALIZED VIEW IF NOT EXISTS timeline.patient_timeline AS
    SELECT
        id,
        canonical_patient_id,
        event_type,
        payload,
        event_time
    FROM timeline.timeline_events
    ORDER BY event_time DESC
WITH NO DATA;

-- Unique index required for REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS patient_timeline_id_idx
    ON timeline.patient_timeline (id);
