CREATE TABLE IF NOT EXISTS patient_event_reconciliation.processed_messages (
    message_id   TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Durable event log: one row per incoming source event, append-only, never updated.
-- Exists because NATS core does not persist messages — if this service restarts or the
-- debounce window needs replaying, there is no way to re-read from the bus.
-- This table is the persistence layer that makes NATS core behave like a durable stream.
CREATE TABLE IF NOT EXISTS patient_event_reconciliation.event_logs (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID   NOT NULL,
    source_system_id     BIGINT NOT NULL,
    message_id           TEXT   NOT NULL,
    event_type           TEXT   NOT NULL,
    payload              JSONB  NOT NULL,
    occurred_at          TIMESTAMPTZ NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS patient_event_reconciliation.pending_publish (
    id                   BIGSERIAL   PRIMARY KEY,
    canonical_patient_id UUID        NOT NULL,
    last_event_log_id    BIGINT      NOT NULL REFERENCES patient_event_reconciliation.event_logs (id),
    scheduled_after      TIMESTAMPTZ NOT NULL,
    ceiling_at           TIMESTAMPTZ NOT NULL,
    published_at         TIMESTAMPTZ,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Partial index: only indexes unpublished rows (published_at IS NULL).
-- Keeps the index small as published rows are excluded — fast lookup for the active debounce window.
CREATE INDEX IF NOT EXISTS pending_publish_active_idx
    ON patient_event_reconciliation.pending_publish (canonical_patient_id, last_event_log_id)
    WHERE published_at IS NULL;

-- Merged output: one row per debounce window, produced after reconciliation logic runs
CREATE TABLE IF NOT EXISTS patient_event_reconciliation.resolved_events (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID     NOT NULL,
    source_system_ids    BIGINT[] NOT NULL,
    from_event_log_id    BIGINT   NOT NULL REFERENCES patient_event_reconciliation.event_logs (id),
    to_event_log_id      BIGINT   NOT NULL REFERENCES patient_event_reconciliation.event_logs (id),
    payload              JSONB    NOT NULL,
    resolution_log       TEXT     NOT NULL,
    occurred_at          TIMESTAMPTZ NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS patient_event_reconciliation.reconciliation_conflicts (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID     NOT NULL,
    source_system_ids    BIGINT[] NOT NULL,
    conflict_type        TEXT     NOT NULL,
    detail               JSONB    NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
