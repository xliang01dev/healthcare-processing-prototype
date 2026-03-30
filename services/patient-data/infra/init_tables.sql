CREATE TABLE IF NOT EXISTS patient_data.patients (
    canonical_patient_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shared_identifier     TEXT NOT NULL UNIQUE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS patient_data.source_systems (
    source_system_id   BIGSERIAL PRIMARY KEY,
    source_system_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS patient_data.source_identities (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID   NOT NULL REFERENCES patient_data.patients (canonical_patient_id),
    source_system_id     BIGINT NOT NULL REFERENCES patient_data.source_systems (source_system_id),
    source_patient_id    TEXT   NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_system_id, source_patient_id)
);

CREATE TABLE IF NOT EXISTS patient_data.golden_records (
    canonical_patient_id UUID        PRIMARY KEY REFERENCES patient_data.patients (canonical_patient_id),
    source_system_ids    BIGINT[]    NOT NULL,
    given_name           TEXT,
    family_name          TEXT,
    date_of_birth        DATE,
    gender               TEXT,
    record_version       BIGINT      NOT NULL DEFAULT 1,
    last_reconciled_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO patient_data.source_systems (source_system_name) VALUES
    ('Medicare'),
    ('Hospital'),
    ('Labs')
ON CONFLICT DO NOTHING;
