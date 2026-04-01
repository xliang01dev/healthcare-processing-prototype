import json
import logging

from datetime import datetime, timedelta, timezone
from shared.data_provider import DataProvider
from patient_event_models import EventLog, PendingPublish

logger = logging.getLogger(__name__)


class PatientEventReconciliationDataProvider(DataProvider):
    """
    Postgres access for the Patient Event Reconciliation service.
    Schema: patient_event_reconciliation (processed_messages, event_logs, pending_publish_debouncer, resolved_events, reconciliation_conflicts)
    """

    async def has_event_log(self, message_id: str) -> bool:
        logger.info("has_event_log: message_id=%s", message_id)
        self.execute("SELECT 1 FROM patient_event_reconciliation.event_logs WHERE message_id = %s", (message_id,))
        result = self.fetchone()
        return result is not None

    async def insert_event_log(self, event: dict) -> int:
        logger.info("insert_event_log: canonical_patient_id=%s event_type=%s", event.get("canonical_patient_id"), event.get("event_type"))
        sql = """
            INSERT INTO patient_event_reconciliation.event_logs
            (canonical_patient_id, source_system_id, message_id, event_type, payload, source_system_event_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """
        event_log_id = self.execute(sql, (
            event.get("canonical_patient_id"),
            event.get("source_system_id"),
            event.get("message_id"),
            event.get("event_type"),
            json.dumps(event.get("payload")),
            event.get("source_system_event_at"),
        ))
        return event_log_id

    async def fetch_event_log_between(self, canonical_patient_id: str, from_event_log_id: int, to_event_log_id: int) -> list[EventLog]:
        logger.info("fetch_event_log_between: canonical_patient_id=%s from_event_log_id=%s to_event_log_id=%s", canonical_patient_id, from_event_log_id, to_event_log_id)
        sql = """
            SELECT id, canonical_patient_id, source_system_id, message_id, event_type, payload, source_system_event_at, created_at
            FROM patient_event_reconciliation.event_logs
            WHERE canonical_patient_id = %s AND id >= %s AND id <= %s
            ORDER BY id ASC
        """
        self.execute(sql, (canonical_patient_id, from_event_log_id, to_event_log_id))
        rows = self.fetchall()
        return [
            EventLog(
                id=row[0],
                canonical_patient_id=row[1],
                source_system_id=row[2],
                message_id=row[3],
                event_type=row[4],
                payload=json.loads(row[5]),
                source_system_event_at=row[6],
                created_at=row[7],
            )
            for row in rows
        ]
    
    async def fetch_pending_publish(self, canonical_patient_id: str) -> PendingPublish:
        logger.info("fetch_pending_publish: canonical_patient_id=%s", canonical_patient_id)
        sql = """
            SELECT id, canonical_patient_id, first_event_log_id, last_event_log_id, scheduled_after, ceiling_at, published_at, updated_at
            FROM patient_event_reconciliation.pending_publish_debouncer
            WHERE canonical_patient_id = %s AND published_at IS NULL
        """
        self.execute(sql, (canonical_patient_id,))
        row = self.fetchone()
        if row:
            return PendingPublish(
                id=row[0],
                canonical_patient_id=row[1],
                first_event_log_id=row[2],
                last_event_log_id=row[3],
                scheduled_after=row[4],
                ceiling_at=row[5],
                published_at=row[6],
                updated_at=row[7],
            )
        else:
            return None

    async def insert_pending_publish(self, canonical_patient_id: str, event_log_id: int, scheduled_after: datetime, ceiling_at: datetime) -> None:
        logger.info(
            "insert_pending_publish: canonical_patient_id=%s event_log_id=%s scheduled_after=%s ceiling_at=%s",
            canonical_patient_id, event_log_id, scheduled_after, ceiling_at
        )
        sql = """
            INSERT INTO patient_event_reconciliation.pending_publish_debouncer
            (canonical_patient_id, first_event_log_id, last_event_log_id, scheduled_after, ceiling_at)
            VALUES (%s, %s, %s, %s, %s)
        """
        await self.execute(sql, (
            canonical_patient_id,
            event_log_id,
            event_log_id,
            scheduled_after,
            ceiling_at
        ))

    async def update_pending_publish(self, canonical_patient_id: str, event_log_id: int, scheduled_after: datetime) -> None:
        logger.info(
            "update_pending_publish: canonical_patient_id=%s event_log_id=%s scheduled_after=%s",
            canonical_patient_id, event_log_id, scheduled_after,
        )
        sql = """
            UPDATE patient_event_reconciliation.pending_publish_debouncer
            SET last_event_log_id = %s,
                scheduled_after = %s,
                updated_at = NOW()
            WHERE canonical_patient_id = %s AND published_at IS NULL
        """
        await self.execute(sql, (
            event_log_id,
            scheduled_after,
            canonical_patient_id
        ))

    async def insert_resolved_event(self, event: dict) -> None:
        logger.info("insert_resolved_event: canonical_patient_id=%s", event.get("canonical_patient_id"))
        # TODO: INSERT INTO patient_event_reconciliation.resolved_events
        #   (canonical_patient_id, source_system_ids, from_event_log_id, to_event_log_id, payload, resolution_log, source_system_event_at)
        #   VALUES ($1, $2, $3, $4, $5, $6, $7);

    async def fetch_conflicts(self, canonical_patient_id: str, page: int, page_size: int) -> list:
        logger.info("fetch_conflicts: canonical_patient_id=%s page=%s page_size=%s", canonical_patient_id, page, page_size)
        # TODO: SELECT * FROM patient_event_reconciliation.reconciliation_conflicts
        #   WHERE canonical_patient_id = $1
        #   ORDER BY created_at DESC
        #   LIMIT $2 OFFSET $3;
        return []

    async def insert_conflict(self, conflict: dict) -> None:
        logger.info("insert_conflict: canonical_patient_id=%s conflict_type=%s", conflict.get("canonical_patient_id"), conflict.get("conflict_type"))
        # TODO: INSERT INTO patient_event_reconciliation.reconciliation_conflicts
        #   (canonical_patient_id, source_system_ids, conflict_type, detail)
        #   VALUES ($1, $2, $3, $4);
