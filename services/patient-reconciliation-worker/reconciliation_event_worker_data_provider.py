import json
import logging

from datetime import datetime
from shared.data_provider import DataProvider
from patient_event_models import EventLog


logger = logging.getLogger(__name__)


class ReconciliationEventWorkerDataProvider(DataProvider):
    """
    Postgres access for the Reconciliation Event Worker service.
    Reads from patient_event_reconciliation schema (event_logs table).
    """

    @staticmethod
    def _parse_datetime(value):
        """Parse ISO string to datetime if needed."""
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value

    async def fetch_event_log_between(self, canonical_patient_id: str, from_event_log_id: int, to_event_log_id: int) -> list[EventLog]:
        """Fetch event logs in a range for a patient."""
        logger.info("fetch_event_log_between: canonical_patient_id=%s from_event_log_id=%s to_event_log_id=%s", canonical_patient_id, from_event_log_id, to_event_log_id)
        sql = """
            SELECT id, canonical_patient_id, source_system_id, message_id, event_type, payload, source_system_occurred_at, created_at
            FROM patient_event_reconciliation.event_logs
            WHERE canonical_patient_id = $1 AND id >= $2 AND id <= $3
            ORDER BY id ASC
        """
        rows = await self.fetch_rows(sql, canonical_patient_id, from_event_log_id, to_event_log_id)
        return [
            EventLog(
                id=row[0],
                canonical_patient_id=row[1],
                source_system_id=row[2],
                message_id=row[3],
                event_type=row[4],
                payload=json.loads(row[5]),
                source_system_occurred_at=row[6],
                created_at=row[7],
            )
            for row in rows
        ]
