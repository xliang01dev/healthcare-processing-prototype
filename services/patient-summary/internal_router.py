import logging

from fastapi import APIRouter

from patient_summary_service import PatientSummaryService
from shared.singleton_store import get_singleton

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/internal/patient/{canonical_patient_id}/recommendation")
async def get_recommendation(canonical_patient_id: str):
    logger.info("GET /internal/patient/%s/recommendation", canonical_patient_id)
    return await get_singleton(PatientSummaryService).fetch_latest_recommendation(canonical_patient_id)


@router.get("/internal/patient/{canonical_patient_id}/recommendations")
async def get_recommendations(canonical_patient_id: str, page: int = 1, page_size: int = 20):
    logger.info("GET /internal/patient/%s/recommendations page=%s page_size=%s", canonical_patient_id, page, page_size)
    return await get_singleton(PatientSummaryService).fetch_recommendations(canonical_patient_id, page, page_size)


@router.post("/internal/patient/recommendations")
async def refresh_recommendation(body: dict):
    canonical_patient_id = body.get("canonical_patient_id", "")
    logger.info("POST /internal/patient/recommendations canonical_patient_id=%s", canonical_patient_id)
    return await get_singleton(PatientSummaryService).run_batch_for_patient(canonical_patient_id)
