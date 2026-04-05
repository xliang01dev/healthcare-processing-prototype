import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from patient_event_reconciliation_data_provider import PatientEventReconciliationDataProvider
from shared.message_bus import MessageBus

logger = logging.getLogger(__name__)


class PatientEventReconciliationService:
    def __init__(
            self,
            data_provider: PatientEventReconciliationDataProvider,
            bus: MessageBus
        ) -> None:
        self.data_provider = data_provider
        self.bus = bus

    async def fetch_conflicts(self, canonical_patient_id: str, page: int, page_size: int) -> list:
        logger.info("fetch_conflicts: canonical_patient_id=%s page=%s page_size=%s", canonical_patient_id, page, page_size)
        return await self.data_provider.fetch_conflicts(canonical_patient_id, page, page_size)

    async def handle_reconcile_event(self, msg) -> None:
        try:
            logger.info("handle_reconcile_event: subject=%s data=%s", msg.subject, msg.data)
            json_data = json.loads(msg.data.decode())
            message_id = json_data.get("message_id")

            # Check idempotency: if event_log already exists for this message_id, skip.
            if await self.data_provider.has_event_log(message_id):
                logger.info("Message %s already processed, skipping", message_id)
                await msg.ack()
                return

            canonical_patient_id = json_data.get("canonical_patient_id")
            # Insert event log before reconciliation
            event_log_id = await self.data_provider.insert_event_log(json_data)
            current_time = datetime.now(timezone.utc)

            # Manage debounce window with row locking to prevent race conditions
            async with self.data_provider.writer_transaction() as conn:
                pending_publish = await self.data_provider.fetch_pending_publish_with_lock(canonical_patient_id, conn)
                debounce_scheduled_after = datetime.now(timezone.utc) + timedelta(seconds=5)

                # If there is an existing pending publish with a future deadline, extend the debounce window
                if pending_publish:
                    # Still within debounce window so update schedule
                    if current_time < pending_publish.scheduled_after:
                        await self.data_provider.update_pending_publish_tx(
                            canonical_patient_id,
                            event_log_id,
                            min(debounce_scheduled_after, pending_publish.ceiling_at),
                            conn
                        )
                    # Outside of debounce window: publish task to work queue
                    else:
                        await self.data_provider.update_pending_published_at_tx(
                            canonical_patient_id=canonical_patient_id,
                            published_at=datetime.now(timezone.utc),
                            conn=conn
                        )
                        # Publish reconciliation task to JetStream work queue
                        await self.bus.publish_stream(
                            topic="reconciliation.tasks",
                            payload={
                                "id": str(uuid4()),
                                "canonical_patient_id": canonical_patient_id,
                                "start_event_log_id": pending_publish.first_event_log_id,
                                "end_event_log_id": pending_publish.last_event_log_id,
                            }
                        )

                # Create a new debounce window if there isn't one or if we're outside the existing debounce window
                if not pending_publish or current_time >= pending_publish.scheduled_after:
                    max_schedule_after = datetime.now(timezone.utc) + timedelta(minutes=30)
                    await self.data_provider.insert_pending_publish_tx(
                        canonical_patient_id,
                        event_log_id,
                        min(debounce_scheduled_after, max_schedule_after),
                        max_schedule_after,
                        conn
                    )

            await msg.ack()
        except Exception as e:
            logger.error("handle_reconcile_event failed: %s", e, exc_info=True)
            await msg.nak()
