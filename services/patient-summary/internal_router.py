from fastapi import APIRouter

from patient_summary_service import PatientSummaryService
from shared.singleton_store import get_singleton

router = APIRouter()


@router.get("/internal/patient/{canonical_patient_id}/recommendation")
async def get_recommendation(canonical_patient_id: str):
    return await get_singleton(PatientSummaryService).fetch_latest_recommendation(canonical_patient_id)


@router.get("/internal/patient/{canonical_patient_id}/recommendations")
async def get_recommendations(canonical_patient_id: str, page: int = 1, page_size: int = 20):
    return await get_singleton(PatientSummaryService).fetch_recommendations(canonical_patient_id, page, page_size)


@router.post("/internal/patient/recommendations")
async def refresh_recommendation(body: dict):
    return await get_singleton(PatientSummaryService).run_batch_for_patient(body.get("canonical_patient_id", ""))
