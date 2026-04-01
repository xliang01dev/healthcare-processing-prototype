import logging

from fastapi import APIRouter

from ingest_service import IngestService
from shared.singleton_store import get_singleton

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ingest")
async def ingest_event(body: dict):
    """
    Ingest a patient event from a source system.

    Body must include a 'source' field: one of 'medicare', 'hospital', 'labs'
    """
    # Extract source from body
    source = body.get("source")

    if not source:
        return {"error": "Missing 'source' field in request body"}

    # Map source name to full source identifier
    source_map = {
        "medicare": "source-medicare",
        "hospital": "source-hospital",
        "labs": "source-labs",
    }

    if source not in source_map:
        return {
            "error": f"Invalid source '{source}'. Must be one of: medicare, hospital, labs"
        }

    source_id = source_map[source]
    logger.info("POST /ingest source=%s body=%s", source, body)
    return await get_singleton(IngestService).ingest_event(source_id, body)


@router.post("/hydrate")
async def hydrate_patient(body: dict):
    """
    Hydrate a patient record (MPI initialization).

    Body must include: medicare_id, first_name, last_name, date_of_birth, gender
    """
    required_fields = ["medicare_id", "first_name", "last_name", "date_of_birth", "gender"]
    missing_fields = [field for field in required_fields if field not in body]

    if missing_fields:
        return {
            "error": f"Missing required fields: {', '.join(missing_fields)}"
        }

    logger.info("POST /hydrate body=%s", body)
    return await get_singleton(IngestService).hydrate_patient(body)
