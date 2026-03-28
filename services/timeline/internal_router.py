from fastapi import APIRouter

from shared.singleton_store import get_singleton
from timeline_service import TimelineService

router = APIRouter()


@router.get("/internal/patient/timeline")
async def get_patient_timeline(canonical_patient_id: str = "", page: int = 1, page_size: int = 100):
    return await get_singleton(TimelineService).fetch_patient_timeline(canonical_patient_id, page, page_size)
