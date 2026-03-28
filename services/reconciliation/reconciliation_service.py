from reconciliation_data_provider import ReconciliationDataProvider


class ReconciliationService:
    def __init__(self, data_provider: ReconciliationDataProvider) -> None:
        self.data_provider = data_provider

    async def handle_raw_event(self, msg) -> None:
        # TODO: Check idempotency against reconciliation.processed_messages (message_id lookup).
        # TODO: Call MPI GET /internal/patient/resolve with exponential backoff:
        #   attempt 1 → immediate, 2 → 100ms, 3 → 200ms, 4 → 400ms, 5 → 800ms → dead-letter on failure.
        # TODO: Apply versioning, deduplication, void handling. See architecture Section 2.
        # TODO: Write event to reconciliation.reconciliation_events.
        # TODO: Publish reconciled event to the message bus.
        pass
