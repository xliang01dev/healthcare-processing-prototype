# Checkpoint — MPI Table Schema (mvp-tables)

## Task

Review and correct the user's proposed three-table MPI schema, then write the corrected schema
to `sdlc/plans/mvp-tables.md`.

## Plan file

`/Volumes/Files/Development/Service/Health/learning-healthcare-processing/sdlc/plans/mvp-tables.md`

## Decisions made

### mpi_source_system
- Removed the proposed `source_id (varchar)` column — it had no PK constraint and was inconsistent
  with the FK in `mpi_source_identities`.
- `source_system TEXT PRIMARY KEY` is the natural key for a three-row controlled vocabulary table.
  No surrogate key added.

### mpi_patients
- `canonical_patient_id` changed from `varchar` to `UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- `shared_identifier` (MBI) is nullable (Source C may omit it) but has a `UNIQUE` constraint —
  required for the `ON CONFLICT (shared_identifier) DO NOTHING` atomic upsert pattern.
- `modified_at` column retained; application or trigger must update it explicitly.

### mpi_source_identities
- Added `source_patient_id TEXT NOT NULL` — the ID the source assigned to this patient.
  This was missing from the proposed schema and is the primary lookup key for incoming events.
- `source_id UUID` FK corrected to `source_system TEXT` FK referencing `mpi_source_system(source_system)`.
- Added `BIGSERIAL` surrogate PK.
- Unique constraint on `(source_system, source_patient_id)` enforces one canonical ID per source record.
- Added `idx_mpi_name_dob` for fallback name+DOB lookup.
- Added `idx_mpi_canonical_patient` for the reverse UUID → all-source-identities lookup.

## Status

Schema written and approved. Ready for implementation by agent-code.
