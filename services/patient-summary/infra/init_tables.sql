CREATE TABLE IF NOT EXISTS patient_summary.recommendations (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID NOT NULL,
    summary              TEXT NOT NULL,
    risk_tier            TEXT NOT NULL CHECK (risk_tier IN ('low', 'medium', 'high', 'critical')),
    content_hash         TEXT NOT NULL,
    generated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS patient_summary.pending_assessments (
    canonical_patient_id UUID PRIMARY KEY,
    scheduled_after      TIMESTAMPTZ NOT NULL,
    status               TEXT NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'processing', 'done', 'failed')),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
