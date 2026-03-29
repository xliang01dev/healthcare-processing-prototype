from fastapi import APIRouter

from patient_event_reconciliation_service import PatientEventReconciliationService
from shared.singleton_store import get_singleton

router = APIRouter()


@router.get("/internal/patient/{canonical_patient_id}/conflicts")
async def get_patient_conflicts(canonical_patient_id: str, page: int = 1, page_size: int = 20):
    return await get_singleton(PatientEventReconciliationService).fetch_conflicts(canonical_patient_id, page, page_size)
