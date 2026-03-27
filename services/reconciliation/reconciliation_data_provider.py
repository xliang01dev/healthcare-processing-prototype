import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

from data_provider import DataProvider


class ReconciliationDataProvider(DataProvider):
    """
    Postgres access for the Reconciliation service.
    Schema: reconciliation (processed_messages, reconciliation_events, reconciliation_conflicts)
    """

    async def is_message_processed(self, message_id: str) -> bool:
        # TODO: SELECT 1 FROM reconciliation.processed_messages WHERE message_id = $1;
        return False

    async def mark_message_processed(self, message_id: str) -> None:
        # TODO: INSERT INTO reconciliation.processed_messages (message_id, processed_at)
        #   VALUES ($1, NOW()) ON CONFLICT DO NOTHING;
        pass

    async def insert_reconciliation_event(self, event: dict) -> None:
        # TODO: INSERT INTO reconciliation.reconciliation_events
        #   (canonical_patient_id, source_system, event_type, payload, occurred_at)
        #   VALUES ($1, $2, $3, $4, $5);
        pass

    async def fetch_conflicts(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> list:
        # TODO: SELECT * FROM reconciliation.reconciliation_conflicts
        #   WHERE canonical_patient_id = $1
        #   ORDER BY created_at DESC
        #   LIMIT $2 OFFSET $3;
        return []

    async def insert_conflict(self, conflict: dict) -> None:
        # TODO: INSERT INTO reconciliation.reconciliation_conflicts
        #   (canonical_patient_id, conflict_type, detail, created_at)
        #   VALUES ($1, $2, $3, NOW());
        pass
