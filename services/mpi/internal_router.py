from fastapi import APIRouter

from mpi_service import MpiService
from shared.singleton_store import get_singleton

router = APIRouter()


@router.get("/internal/patient/resolve")
async def resolve_patient(source_system: str = "", source_patient_id: str = ""):
    return await get_singleton(MpiService).resolve_patient(source_system, source_patient_id)
