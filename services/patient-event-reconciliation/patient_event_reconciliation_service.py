from patient_event_reconciliation_data_provider import PatientEventReconciliationDataProvider
from shared.message_bus import MessageBus


class PatientEventReconciliationService:
    def __init__(self, data_provider: PatientEventReconciliationDataProvider, bus: MessageBus) -> None:
        self.data_provider = data_provider
        self.bus = bus

    async def fetch_conflicts(self, canonical_patient_id: str, page: int, page_size: int) -> list:
        return await self.data_provider.fetch_conflicts(canonical_patient_id, page, page_size)

    async def handle_reconcile_event(self, msg) -> None:
        # TODO: Check idempotency against patient_event_reconciliation.processed_messages (message_id lookup).
        # TODO: canonical_patient_id is already resolved — extract from msg subject (reconcile.{canonical_patient_id}).
        # TODO: Append to event_logs via data_provider.insert_event_log().
        # TODO: Upsert pending_publish via data_provider.upsert_pending_publish() to reset debounce window.
        # TODO: When debounce expires (scheduled_after ≤ NOW() or ceiling_at ≤ NOW()):
        #   Apply versioning, deduplication, void handling across event_logs window.
        #   Write merged result via data_provider.insert_resolved_event().
        #   Publish to reconciled.events via self.bus.
        #   Mark pending_publish.published_at = NOW().
        pass
