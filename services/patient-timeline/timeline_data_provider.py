from shared.data_provider import DataProvider


class TimelineDataProvider(DataProvider):
    """
    Postgres access for the Patient Timeline service.
    Schema: patient_timeline (timeline_events, patient_timeline, pending_processing)
    """

    async def refresh_patient_timeline(self) -> None:
        # TODO: REFRESH MATERIALIZED VIEW CONCURRENTLY patient_timeline.patient_timeline;
        #   Must complete BEFORE publishing to timeline.updated (refresh-then-publish rule).
        pass

    async def fetch_patient_timeline(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> list:
        # TODO: SELECT * FROM patient_timeline.patient_timeline
        #   WHERE canonical_patient_id = $1
        #   ORDER BY event_time DESC
        #   LIMIT $2 OFFSET $3;
        return []

