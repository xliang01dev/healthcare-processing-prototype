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
