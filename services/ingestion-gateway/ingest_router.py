from fastapi import APIRouter

from ingest_service import IngestService
from shared.singleton_store import get_singleton

router = APIRouter()


@router.post("/ingest/source-a")
async def ingest_source_a(body: dict):
    return await get_singleton(IngestService).ingest_event("source-a", body)


@router.post("/ingest/source-b")
async def ingest_source_b(body: dict):
    return await get_singleton(IngestService).ingest_event("source-b", body)


@router.post("/ingest/source-c")
async def ingest_source_c(body: dict):
    return await get_singleton(IngestService).ingest_event("source-c", body)
