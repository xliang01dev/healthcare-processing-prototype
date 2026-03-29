import logging

from shared.data_provider import DataProvider

logger = logging.getLogger(__name__)


class TimelineDataProvider(DataProvider):
    """
    Postgres access for the Patient Timeline service.
    Schema: patient_timeline (timeline_events, patient_timeline)
    """

    async def refresh_patient_timeline(self) -> None:
        logger.info("refresh_patient_timeline")
        # TODO: REFRESH MATERIALIZED VIEW CONCURRENTLY patient_timeline.patient_timeline;
        #   Must complete BEFORE publishing to timeline.updated (refresh-then-publish rule).

    async def fetch_patient_timeline(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> list:
        logger.info("fetch_patient_timeline: canonical_patient_id=%s page=%s page_size=%s", canonical_patient_id, page, page_size)
        # TODO: SELECT * FROM patient_timeline.patient_timeline
        #   WHERE canonical_patient_id = $1
        #   ORDER BY event_time DESC
        #   LIMIT $2 OFFSET $3;
        return []
