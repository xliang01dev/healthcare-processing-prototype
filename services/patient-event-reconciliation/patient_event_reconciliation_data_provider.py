from shared.data_provider import DataProvider


class PatientEventReconciliationDataProvider(DataProvider):
    """
    Postgres access for the Patient Event Reconciliation service.
    Schema: patient_event_reconciliation (processed_messages, event_logs, pending_publish, resolved_events, reconciliation_conflicts)
    """

    async def is_message_processed(self, message_id: str) -> bool:
        # TODO: SELECT 1 FROM patient_event_reconciliation.processed_messages WHERE message_id = $1;
        return False

    async def mark_message_processed(self, message_id: str) -> None:
        # TODO: INSERT INTO patient_event_reconciliation.processed_messages (message_id, processed_at)
        #   VALUES ($1, NOW()) ON CONFLICT DO NOTHING;
        pass

    async def insert_event_log(self, event: dict) -> int:
        # TODO: INSERT INTO patient_event_reconciliation.event_logs
        #   (canonical_patient_id, source_system_id, message_id, event_type, payload, occurred_at)
        #   VALUES ($1, $2, $3, $4, $5, $6) RETURNING id;
        return 0

    async def upsert_pending_publish(self, canonical_patient_id: str, event_log_id: int, scheduled_after, ceiling_at) -> None:
        # TODO: If active row exists (published_at IS NULL AND ceiling_at > NOW()):
        #   UPDATE SET last_event_log_id = $2, scheduled_after = $3, updated_at = NOW()
        # If no active row:
        #   INSERT (canonical_patient_id, last_event_log_id, scheduled_after, ceiling_at)
        pass

    async def insert_resolved_event(self, event: dict) -> None:
        # TODO: INSERT INTO patient_event_reconciliation.resolved_events
        #   (canonical_patient_id, source_system_ids, from_event_log_id, to_event_log_id, payload, resolution_log, occurred_at)
        #   VALUES ($1, $2, $3, $4, $5, $6, NOW());
        pass

    async def fetch_conflicts(self, canonical_patient_id: str, page: int, page_size: int) -> list:
        # TODO: SELECT * FROM patient_event_reconciliation.reconciliation_conflicts
        #   WHERE canonical_patient_id = $1
        #   ORDER BY created_at DESC
        #   LIMIT $2 OFFSET $3;
        return []

    async def insert_conflict(self, conflict: dict) -> None:
        # TODO: INSERT INTO patient_event_reconciliation.reconciliation_conflicts
        #   (canonical_patient_id, source_system_ids, conflict_type, detail)
        #   VALUES ($1, $2, $3, $4);
        pass
