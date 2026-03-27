from fastapi import APIRouter

from mpi_service import MpiService

router = APIRouter()
service = MpiService()


@router.get("/internal/patient/resolve")
async def resolve_patient(source_system: str = "", source_patient_id: str = ""):
    return await service.resolve_patient(source_system, source_patient_id)
