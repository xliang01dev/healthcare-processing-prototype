from fastapi import APIRouter

from ingest_service import IngestService

router = APIRouter()
service = IngestService()


@router.post("/ingest/source-a")
async def ingest_source_a(body: dict):
    return await service.ingest_event("source-a", body)


@router.post("/ingest/source-b")
async def ingest_source_b(body: dict):
    return await service.ingest_event("source-b", body)


@router.post("/ingest/source-c")
async def ingest_source_c(body: dict):
    return await service.ingest_event("source-c", body)
