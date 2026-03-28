CREATE TABLE IF NOT EXISTS mpi.mpi_patients (
    canonical_patient_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shared_identifier     TEXT NOT NULL UNIQUE,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mpi.mpi_source_identities (
    id                   BIGSERIAL PRIMARY KEY,
    canonical_patient_id UUID NOT NULL REFERENCES mpi.mpi_patients (canonical_patient_id),
    source_system        TEXT NOT NULL,
    source_patient_id    TEXT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_system, source_patient_id)
);
