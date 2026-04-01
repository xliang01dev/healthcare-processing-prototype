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


class PatientCoordinatorService:
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

    async def get_patient_info(self, canonical_patient_id: str, medicare_id: str) -> PatientInfoResponse:
        logger.info("get_patient_info: canonical_patient_id=%s", canonical_patient_id)
        try:
            url = f"{self.patient_data_url}/internal/patient/{canonical_patient_id}/golden-record"
            response = await self.http_client.get(url)
            response.raise_for_status()

            response_json = response.json()
            response_json["medicare_id"] = medicare_id

            patient_info_response = PatientInfoResponse.model_validate(response_json)
            patient_info_response.medicare_id = medicare_id
            
            return patient_info_response
        except httpx.HTTPError as e:
            logger.error("Failed to fetch patient info: %s", e)
            return PatientInfoResponse()

    async def resolve_medicare_id_to_canonical(self, medicare_id: str) -> str | None:
        """Resolve medicare_id to canonical_patient_id via patient_data service."""
        logger.info("resolve_medicare_id_to_canonical: medicare_id=%s", medicare_id)
        try:
            # Query patient_data service to resolve medicare_id to canonical_patient_id
            # Assuming there's an endpoint like /internal/patient/resolve?medicare_id={id}
            # For now, we'll use a direct query to get the canonical_patient_id
            url = f"{self.patient_data_url}/internal/patient/resolve"
            params = {"medicare_id": medicare_id}
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("canonical_patient_id")
        except httpx.HTTPError as e:
            logger.error("Failed to resolve medicare_id: %s", e)
            return None

    async def resolve_canonical_to_medicare_id(self, canonical_patient_id: str) -> str | None:
        """Resolve medicare_id to canonical_patient_id via patient_data service."""
        logger.info("resolve_canonical_to_medicare_id: medicare_id=%s", canonical_patient_id)
        try:
            url = f"{self.patient_data_url}/internal/patient/resolve"
            params = {"canonical_patient_id": canonical_patient_id}
            response = await self.http_client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("medicare_id")
        except httpx.HTTPError as e:
            logger.error("Failed to resolve medicare_id: %s", e)
            return None

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
