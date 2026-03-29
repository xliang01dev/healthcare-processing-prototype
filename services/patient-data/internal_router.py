from fastapi import APIRouter, HTTPException

from patient_data_service import PatientDataService
from shared.singleton_store import get_singleton

router = APIRouter()


@router.get("/internal/patient/{canonical_patient_id}/golden-record")
async def get_golden_record(canonical_patient_id: str):
    record = await get_singleton(PatientDataService).fetch_golden_record(canonical_patient_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Golden record not found")
    return record
