# MPI Database Schema — Master Patient Index Tables

## Summary

This document defines the three Postgres tables that back the Master Patient Index (MPI) service.
The MPI resolves source-specific patient identifiers from Source A, B, and C into a single
`canonical_patient_id` (UUID) used by all downstream services. No downstream service ever sees
a source-local ID — only the canonical UUID.

## Design Notes — Corrections from Proposed Schema

### 1. Primary key types must be consistent

The proposed schema mixed `varchar` and `UUID` for primary and foreign keys across tables.
`canonical_patient_id` must be `UUID` — the atomic upsert uses `gen_random_uuid()` and all
downstream services treat it as a UUID. Source-local IDs are `TEXT`.

### 2. mpi_source_system — remove source_id, make source_system the primary key

The proposed `source_id (varchar)` column on `mpi_source_system` had no PRIMARY KEY constraint
and was unused. `mpi_source_identities.source_id` was typed `UUID`, which cannot FK to a `varchar`
column, and the join would have failed at runtime.

`source_system` (the name: `source-a`, `source-b`, `source-c`) is a small, stable, controlled
vocabulary. Making it the `TEXT PRIMARY KEY` eliminates a pointless surrogate key and an extra join.
`mpi_source_identities` references it directly by the text name.

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
- `mpi_source_identities(source_system, source_patient_id)` — covered by the UNIQUE constraint.
- `mpi_source_identities(last_name, date_of_birth)` — needed for the fallback name+DOB lookup
  when `shared_identifier` is absent.
- `mpi_source_identities(canonical_patient_id)` — needed to resolve all source identities for a
  given patient (the reverse lookup: UUID → all source rows).

---

## Table Descriptions

### mpi_source_system

A small reference table. One row per data source. The `source_system` text name is the primary key
and is used directly as a foreign key in `mpi_source_identities`. This table is seeded at startup
with the three known sources and does not change at runtime.

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
    source_system  TEXT PRIMARY KEY  -- 'source-a' | 'source-b' | 'source-c'
);

-- Seed values (run once at startup)
INSERT INTO mpi_source_system (source_system) VALUES
    ('source-a'),
    ('source-b'),
    ('source-c')
ON CONFLICT DO NOTHING;


-- ============================================================
-- mpi_patients
-- One row per unique real-world patient.
-- The atomic upsert targets the UNIQUE constraint on
-- shared_identifier to prevent duplicate canonical IDs.
-- ============================================================
CREATE TABLE mpi_patients (
    canonical_patient_id  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    shared_identifier     TEXT         UNIQUE,          -- MBI; nullable (may be absent from Source C)
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
    source_system         TEXT         NOT NULL REFERENCES mpi_source_system(source_system),
    source_patient_id     TEXT         NOT NULL,         -- the ID the source system assigned to this patient
    first_name            TEXT,
    last_name             TEXT,
    date_of_birth         DATE,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    modified_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    UNIQUE (source_system, source_patient_id)            -- one canonical ID per source record, enforced
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

## Relationship Diagram

```
mpi_source_system
    source_system (TEXT, PK)
         |
         | 1
         |
         * (many)
mpi_source_identities
    id                   (BIGSERIAL, PK)
    canonical_patient_id (UUID, FK → mpi_patients)
    source_system        (TEXT, FK → mpi_source_system)
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

When `shared_identifier` is null (Source C, no MBI), the application generates a UUID directly and
inserts without a conflict target. The fallback match against `last_name + date_of_birth` in
`mpi_source_identities` is attempted first; if a match is found the existing `canonical_patient_id`
is used. If no match is found, a new canonical patient is created.
```
