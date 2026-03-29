from patient_data_provider import PatientDataProvider
from shared.message_bus import MessageBus


class PatientDataService:
    def __init__(self, data_provider: PatientDataProvider, bus: MessageBus) -> None:
        self.data_provider = data_provider
        self.bus = bus

    async def handle_hydration_event(self, msg) -> None:
        # TODO: Parse operation (add | update | remove) and patient fields from msg payload.
        # TODO: add    → upsert_patient(shared_identifier), upsert_source_identity(), upsert_golden_record().
        # TODO: update → upsert_golden_record() with updated fields (record_version increments).
        # TODO: remove → soft-delete or tombstone pattern (do not hard-delete canonical records).
        pass

    async def handle_source_event(self, msg) -> None:
        # TODO: Extract source_system_id and source_patient_id from msg payload.
        # TODO: Lookup patient_data.source_identities for (source_system_id, source_patient_id).
        # TODO: If not found → create new canonical_patient_id via upsert_patient(), upsert_source_identity().
        # TODO: upsert_golden_record() with fields from msg payload.
        # TODO: Publish original msg payload + canonical_patient_id to reconcile.{canonical_patient_id}
        #   so reconciliation consumes a partitioned, ordered subject per patient.
        pass

    async def fetch_golden_record(self, canonical_patient_id: str) -> dict | None:
        return await self.data_provider.fetch_golden_record(canonical_patient_id)
