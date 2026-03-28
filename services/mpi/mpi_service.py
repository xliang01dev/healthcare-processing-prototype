from mpi_data_provider import MpiDataProvider


class MpiService:
    def __init__(self, data_provider: MpiDataProvider) -> None:
        self.data_provider = data_provider

    async def handle_hydration_event(self, msg) -> None:
        # TODO: Parse operation (add | update | remove) and shared_identifier from msg payload.
        # TODO: add    → INSERT INTO mpi.mpi_patients (shared_identifier) ON CONFLICT DO NOTHING;
        #               INSERT INTO mpi.mpi_source_identities (canonical_patient_id, source_system, source_patient_id).
        # TODO: update → UPDATE mpi.mpi_patients / mpi.mpi_source_identities for changed fields.
        # TODO: remove → soft-delete or tombstone pattern (do not hard-delete canonical records).
        pass

    async def handle_source_event(self, msg) -> None:
        # TODO: Extract source_system and source_patient_id from msg payload.
        # TODO: Lookup mpi.mpi_source_identities for (source_system, source_patient_id).
        # TODO: If not found → patient not yet correlated; create new canonical_patient_id:
        #   INSERT INTO mpi.mpi_patients (shared_identifier) VALUES (gen_random_uuid()) RETURNING canonical_patient_id;
        #   INSERT INTO mpi.mpi_source_identities (canonical_patient_id, source_system, source_patient_id).
        # TODO: If found → no action needed; reconciliation owns downstream processing.
        pass

    async def resolve_patient(self, source_system: str, source_patient_id: str) -> dict:
        # TODO: Lookup canonical_patient_id from mpi.mpi_source_identities
        #   WHERE source_system = $1 AND source_patient_id = $2.
        # Called by the internal HTTP router (used by reconciliation service).
        return {"canonical_patient_id": None, "status": "stub"}
