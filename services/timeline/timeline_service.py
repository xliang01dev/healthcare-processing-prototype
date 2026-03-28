from timeline_data_provider import TimelineDataProvider


class TimelineService:
    def __init__(self, data_provider: TimelineDataProvider) -> None:
        self.data_provider = data_provider

    async def fetch_patient_timeline(self, canonical_patient_id: str, page: int, page_size: int) -> list:
        return await self.data_provider.fetch_patient_timeline(canonical_patient_id, page, page_size)

    async def handle_reconciled_event(self, msg) -> None:
        # TODO: Call REFRESH MATERIALIZED VIEW CONCURRENTLY timeline.patient_timeline.
        #   This MUST complete BEFORE publishing to timeline.updated (refresh-then-publish rule).
        #   See architecture Section 4.
        # TODO: Upsert timeline.pending_processing, bumping scheduled_after to reset debounce window.
        # TODO: After debounce window expires with no further events, publish timeline updated event to the message bus.
        pass
