class MpiService:
    async def resolve_patient(self, source_system: str, source_patient_id: str) -> dict:
        # TODO: Atomic upsert pattern:
        #   INSERT INTO mpi.mpi_patients (shared_identifier)
        #   VALUES ($mbi) ON CONFLICT (shared_identifier) DO NOTHING;
        #   SELECT canonical_patient_id FROM mpi.mpi_patients WHERE shared_identifier = $mbi;
        # See architecture Section 3.
        return {"canonical_patient_id": None, "status": "stub"}
