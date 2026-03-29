from timeline_data_provider import TimelineDataProvider
from shared.message_bus import MessageBus


class TimelineService:
    def __init__(self, data_provider: TimelineDataProvider, bus: MessageBus) -> None:
        self.data_provider = data_provider
        self.bus = bus

    async def fetch_patient_timeline(self, canonical_patient_id: str, page: int, page_size: int) -> list:
        return await self.data_provider.fetch_patient_timeline(canonical_patient_id, page, page_size)

    async def handle_reconciled_event(self, msg) -> None:
        # TODO: Call data_provider.refresh_patient_timeline() — MUST complete before publishing.
        # TODO: Publish to timeline.updated via self.bus.
        pass
