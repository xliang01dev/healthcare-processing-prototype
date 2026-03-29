import logging

from timeline_data_provider import TimelineDataProvider
from shared.message_bus import MessageBus

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
        # TODO: Call data_provider.refresh_patient_timeline() — MUST complete before publishing.
        # TODO: Publish to timeline.updated via self.bus.
