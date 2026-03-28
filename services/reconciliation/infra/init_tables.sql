CREATE TABLE IF NOT EXISTS reconciliation.processed_messages (
    message_id   TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reconciliation.reconciliation_events (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID NOT NULL,
    source_system        TEXT NOT NULL,
    event_type           TEXT NOT NULL,
    payload              JSONB NOT NULL,
    occurred_at          TIMESTAMPTZ NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS reconciliation.reconciliation_conflicts (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID NOT NULL,
    conflict_type        TEXT NOT NULL,
    detail               JSONB NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
