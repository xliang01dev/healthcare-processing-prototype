import logging

from fastapi import APIRouter

from models import (
    ConflictsResponse,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationsResponse,
    PatientInfoResponse,
    TimelineResponse,
)
from patient_coordinator_service import PatientCoordinatorService
from shared.singleton_store import get_singleton

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/patient")


@router.get("/medicare/{medicare_id}", response_model=PatientInfoResponse)
async def get_patient_info_by_medicare(medicare_id: str):
    """Fetch patient golden record by medicare_id."""
    logger.info("GET /patient/medicare/%s", medicare_id)
    coordinator = get_singleton(PatientCoordinatorService)

    # Resolve medicare_id to canonical_patient_id
    canonical_patient_id = await coordinator.resolve_medicare_id_to_canonical(medicare_id)
    logger.info("_get_patient_info_by_medicare_ canonical_patient_id=%s", canonical_patient_id)
    if canonical_patient_id:
        return await coordinator.get_patient_info(canonical_patient_id, medicare_id)
    return PatientInfoResponse()


@router.get("/{canonical_patient_id}/timelines", response_model=TimelineResponse)
async def get_patient_timelines(
    canonical_patient_id: str, page: int = 1, page_size: int = 20
):
    logger.info("GET /patient/%s/timelines page=%s page_size=%s", canonical_patient_id, page, page_size)
    return await get_singleton(PatientCoordinatorService).get_patient_timelines(canonical_patient_id, page, page_size)


@router.get("/{canonical_patient_id}/recommendation", response_model=RecommendationResponse)
async def get_patient_recommendation(canonical_patient_id: str):
    logger.info("GET /patient/%s/recommendation", canonical_patient_id)
    return await get_singleton(PatientCoordinatorService).get_patient_recommendation(canonical_patient_id)


@router.get("/{canonical_patient_id}/recommendations", response_model=RecommendationsResponse)
async def get_patient_recommendations(
    canonical_patient_id: str, page: int = 1, page_size: int = 20
):
    logger.info("GET /patient/%s/recommendations page=%s page_size=%s", canonical_patient_id, page, page_size)
    return await get_singleton(PatientCoordinatorService).get_patient_recommendations(canonical_patient_id, page, page_size)


@router.get("/{canonical_patient_id}/conflicts", response_model=ConflictsResponse)
async def get_patient_conflicts(
    canonical_patient_id: str, page: int = 1, page_size: int = 20
):
    logger.info("GET /patient/%s/conflicts page=%s page_size=%s", canonical_patient_id, page, page_size)
    return await get_singleton(PatientCoordinatorService).get_patient_conflicts(canonical_patient_id, page, page_size)


@router.post("/recommendations")
async def create_recommendation(body: RecommendationRequest):
    logger.info("POST /patient/recommendations canonical_patient_id=%s", body.canonical_patient_id)
    return await get_singleton(PatientCoordinatorService).refresh_recommendation(body)
