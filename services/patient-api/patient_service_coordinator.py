import logging

import httpx

from models import (
    ConflictsResponse,
    PatientInfoResponse,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationsResponse,
    TimelineResponse,
)

logger = logging.getLogger(__name__)


class PatientServiceCoordinator:
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        patient_data_url: str,
        reconciliation_url: str,
        timeline_url: str,
        patient_summary_url: str,
    ) -> None:
        self.http_client = http_client
        self.patient_data_url = patient_data_url
        self.reconciliation_url = reconciliation_url
        self.timeline_url = timeline_url
        self.patient_summary_url = patient_summary_url

    async def get_patient_info(self, canonical_patient_id: str) -> PatientInfoResponse:
        logger.info("get_patient_info: canonical_patient_id=%s", canonical_patient_id)
        # TODO: GET {patient_data_url}/internal/patient/{canonical_patient_id}/golden-record
        return PatientInfoResponse()

    async def get_patient_timelines(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> TimelineResponse:
        logger.info("get_patient_timelines: canonical_patient_id=%s page=%s page_size=%s", canonical_patient_id, page, page_size)
        # TODO: GET {timeline_url}/internal/patient/timeline?canonical_patient_id={id}&page={page}&page_size={page_size}
        return TimelineResponse()

    async def get_patient_recommendation(
        self, canonical_patient_id: str
    ) -> RecommendationResponse:
        logger.info("get_patient_recommendation: canonical_patient_id=%s", canonical_patient_id)
        # TODO: GET {patient_summary_url}/internal/patient/{canonical_patient_id}/recommendation
        return RecommendationResponse()

    async def get_patient_recommendations(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> RecommendationsResponse:
        logger.info("get_patient_recommendations: canonical_patient_id=%s page=%s page_size=%s", canonical_patient_id, page, page_size)
        # TODO: GET {patient_summary_url}/internal/patient/{canonical_patient_id}/recommendations?page={page}&page_size={page_size}
        return RecommendationsResponse()

    async def get_patient_conflicts(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> ConflictsResponse:
        logger.info("get_patient_conflicts: canonical_patient_id=%s page=%s page_size=%s", canonical_patient_id, page, page_size)
        # TODO: GET {reconciliation_url}/internal/patient/{canonical_patient_id}/conflicts?page={page}&page_size={page_size}
        return ConflictsResponse()

    async def refresh_recommendation(self, body: RecommendationRequest) -> dict:
        logger.info("refresh_recommendation: canonical_patient_id=%s", body.canonical_patient_id)
        # TODO: POST {patient_summary_url}/internal/patient/recommendations
        return {"stub": True}
