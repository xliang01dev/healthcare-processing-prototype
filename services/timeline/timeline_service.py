class TimelineService:
    async def handle_reconciled_event(self, msg) -> None:
        # TODO: Call REFRESH MATERIALIZED VIEW CONCURRENTLY timeline.patient_timeline.
        #   This MUST complete BEFORE publishing to timeline.updated (refresh-then-publish rule).
        #   See architecture Section 4.
        # TODO: Upsert timeline.pending_processing, bumping scheduled_after to reset debounce window.
        # TODO: After debounce window expires with no further events, publish timeline updated event to the message bus.
        pass
