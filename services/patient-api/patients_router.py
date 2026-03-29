from fastapi import APIRouter

from models import (
    ConflictsResponse,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationsResponse,
    PatientInfoResponse,
    TimelineResponse,
)
from patient_service_coordinator import PatientServiceCoordinator
from shared.singleton_store import get_singleton

router = APIRouter(prefix="/v1/patient")


@router.get("/{canonical_patient_id}/info", response_model=PatientInfoResponse)
async def get_patient_info(canonical_patient_id: str):
    return await get_singleton(PatientServiceCoordinator).get_patient_info(canonical_patient_id)


@router.get("/{canonical_patient_id}/timelines", response_model=TimelineResponse)
async def get_patient_timelines(
    canonical_patient_id: str, page: int = 1, page_size: int = 20
):
    return await get_singleton(PatientServiceCoordinator).get_patient_timelines(canonical_patient_id, page, page_size)


@router.get("/{canonical_patient_id}/recommendation", response_model=RecommendationResponse)
async def get_patient_recommendation(canonical_patient_id: str):
    return await get_singleton(PatientServiceCoordinator).get_patient_recommendation(canonical_patient_id)


@router.get("/{canonical_patient_id}/recommendations", response_model=RecommendationsResponse)
async def get_patient_recommendations(
    canonical_patient_id: str, page: int = 1, page_size: int = 20
):
    return await get_singleton(PatientServiceCoordinator).get_patient_recommendations(canonical_patient_id, page, page_size)


@router.get("/{canonical_patient_id}/conflicts", response_model=ConflictsResponse)
async def get_patient_conflicts(
    canonical_patient_id: str, page: int = 1, page_size: int = 20
):
    return await get_singleton(PatientServiceCoordinator).get_patient_conflicts(canonical_patient_id, page, page_size)


@router.post("/recommendations")
async def create_recommendation(body: RecommendationRequest):
    return await get_singleton(PatientServiceCoordinator).refresh_recommendation(body)
