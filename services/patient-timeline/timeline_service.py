import json
import logging

from timeline_data_provider import TimelineDataProvider
from shared.message_bus import MessageBus
from shared.event_models import ReconciledEvent

logger = logging.getLogger(__name__)


class TimelineService:
    def __init__(self, data_provider: TimelineDataProvider, bus: MessageBus) -> None:
        self.data_provider = data_provider
        self.bus = bus

    async def fetch_patient_timeline(self, canonical_patient_id: str, page: int, page_size: int) -> list:
        logger.info("fetch_patient_timeline: canonical_patient_id=%s page=%s page_size=%s", canonical_patient_id, page, page_size)
        return await self.data_provider.fetch_patient_timeline(canonical_patient_id, page, page_size)

    async def handle_reconciled_event(self, msg) -> None:
        logger.info("handle_reconciled_event: data=%s", msg.data)

        # Parse reconciled event from message
        event_data = json.loads(msg.data.decode())
        reconciled_event = ReconciledEvent.model_validate(event_data)

        # Insert the reconciled event into the timeline
        await self.data_provider.insert_reconciled_event(reconciled_event)

        # Refresh materialized view — MUST complete before publishing (refresh-then-publish rule)
        await self.data_provider.refresh_patient_timeline()

        # Publish timeline.updated event
        await self.bus.publish(
            topic="timeline.updated",
            payload=reconciled_event.model_dump_json()
        )

        logger.info("handle_reconciled_event: published timeline.updated for canonical_patient_id=%s", reconciled_event.canonical_patient_id)
