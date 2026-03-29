import logging

from fastapi import APIRouter

from ingest_service import IngestService
from shared.singleton_store import get_singleton

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ingest/source-medicare")
async def ingest_source_medicare(body: dict):
    logger.info("POST /ingest/source-medicare body=%s", body)
    return await get_singleton(IngestService).ingest_event("source-medicare", body)


@router.post("/ingest/source-hospital")
async def ingest_source_hospital(body: dict):
    logger.info("POST /ingest/source-hospital body=%s", body)
    return await get_singleton(IngestService).ingest_event("source-hospital", body)


@router.post("/ingest/source-labs")
async def ingest_source_labs(body: dict):
    logger.info("POST /ingest/source-labs body=%s", body)
    return await get_singleton(IngestService).ingest_event("source-labs", body)
