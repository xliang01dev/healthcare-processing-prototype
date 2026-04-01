import logging

from fastapi import APIRouter, HTTPException

from patient_data_service import PatientDataService
from shared.singleton_store import get_singleton

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/internal/patient/{canonical_patient_id}/golden-record")
async def get_golden_record(canonical_patient_id: str):
    logger.info("GET /internal/patient/%s/golden-record", canonical_patient_id)
    record = await get_singleton(PatientDataService).fetch_golden_record(canonical_patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Golden record not found")
    return record


@router.get("/internal/patient/resolve")
async def resolve_medicare_id(medicare_id: str):
    """Resolve medicare_id to canonical_patient_id."""
    logger.info("GET /internal/patient/resolve medicare_id=%s", medicare_id)
    service = get_singleton(PatientDataService)
    
    patient_info = await service.data_provider.fetch_patient(medicare_id)
    canonical_patient_id = patient_info.canonical_patient_id

    if canonical_patient_id is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"canonical_patient_id": canonical_patient_id}
