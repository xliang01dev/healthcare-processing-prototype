from shared.data_provider import DataProvider


class TimelineDataProvider(DataProvider):
    """
    Postgres access for the Timeline service.
    Schema: timeline (timeline_events, patient_timeline, pending_processing)
    """

    async def refresh_patient_timeline(self) -> None:
        # TODO: REFRESH MATERIALIZED VIEW CONCURRENTLY timeline.patient_timeline;
        #   Must complete BEFORE publishing to timeline.updated (refresh-then-publish rule).
        pass

    async def fetch_patient_timeline(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> list:
        # TODO: SELECT * FROM timeline.patient_timeline
        #   WHERE canonical_patient_id = $1
        #   ORDER BY event_time DESC
        #   LIMIT $2 OFFSET $3;
        return []

    async def upsert_pending_assessment(
        self, canonical_patient_id: str, scheduled_after
    ) -> None:
        # TODO: INSERT INTO timeline.pending_processing
        #   (canonical_patient_id, scheduled_after, status)
        #   VALUES ($1, $2, 'pending')
        #   ON CONFLICT (canonical_patient_id)
        #   DO UPDATE SET scheduled_after = EXCLUDED.scheduled_after;
        #   Bumping scheduled_after resets the debounce window.
        pass

    async def fetch_due_pending_assessments(self) -> list:
        # TODO: SELECT * FROM timeline.pending_processing
        #   WHERE scheduled_after < NOW() AND status = 'pending';
        return []
