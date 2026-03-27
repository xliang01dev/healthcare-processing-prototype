from fastapi import APIRouter

from models import (
    ConflictsResponse,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationsResponse,
    PatientInfoResponse,
    TimelineResponse,
)
from patient_service import PatientService

router = APIRouter(prefix="/v1/patient")
service = PatientService()


@router.get("/{canonical_patient_id}/info", response_model=PatientInfoResponse)
async def get_patient_info(canonical_patient_id: str):
    return await service.get_patient_info(canonical_patient_id)


@router.get("/{canonical_patient_id}/timelines", response_model=TimelineResponse)
async def get_patient_timelines(
    canonical_patient_id: str, page: int = 1, pageSize: int = 20
):
    return await service.get_patient_timelines(canonical_patient_id, page, pageSize)


@router.get("/{canonical_patient_id}/recommendation", response_model=RecommendationResponse)
async def get_patient_recommendation(canonical_patient_id: str):
    return await service.get_patient_recommendation(canonical_patient_id)


@router.get("/{canonical_patient_id}/recommendations", response_model=RecommendationsResponse)
async def get_patient_recommendations(
    canonical_patient_id: str, page: int = 1, pageSize: int = 20
):
    return await service.get_patient_recommendations(canonical_patient_id, page, pageSize)


@router.get("/{canonical_patient_id}/conflicts", response_model=ConflictsResponse)
async def get_patient_conflicts(
    canonical_patient_id: str, page: int = 1, pageSize: int = 20
):
    return await service.get_patient_conflicts(canonical_patient_id, page, pageSize)


@router.post("/recommendations")
async def create_recommendation(body: RecommendationRequest):
    return await service.refresh_recommendation(body)
