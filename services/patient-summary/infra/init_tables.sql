CREATE TABLE IF NOT EXISTS patient_summary.recommendations (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID NOT NULL,
    summary              TEXT NOT NULL,
    risk_tier            TEXT NOT NULL CHECK (risk_tier IN ('low', 'medium', 'high', 'critical')),
    content_hash         TEXT NOT NULL,
    generated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
