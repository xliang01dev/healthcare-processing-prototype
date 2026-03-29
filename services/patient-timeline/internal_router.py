import logging

from fastapi import APIRouter

from shared.singleton_store import get_singleton
from timeline_service import TimelineService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/internal/patient/timeline")
async def get_patient_timeline(canonical_patient_id: str = "", page: int = 1, page_size: int = 100):
    logger.info("GET /internal/patient/timeline canonical_patient_id=%s page=%s page_size=%s", canonical_patient_id, page, page_size)
    return await get_singleton(TimelineService).fetch_patient_timeline(canonical_patient_id, page, page_size)
