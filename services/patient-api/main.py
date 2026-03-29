from contextlib import asynccontextmanager
import logging
import os

import httpx
from fastapi import FastAPI

from shared.singleton_store import register_singleton, remove_singleton
from patient_service_coordinator import PatientServiceCoordinator
import patients_router as patients

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

http_client = httpx.AsyncClient()
register_singleton(PatientServiceCoordinator, PatientServiceCoordinator(
    http_client=http_client,
    patient_data_url=os.getenv("PATIENT_DATA_URL", ""),
    reconciliation_url=os.getenv("RECONCILIATION_URL", ""),
    timeline_url=os.getenv("TIMELINE_URL", ""),
    patient_summary_url=os.getenv("PATIENT_SUMMARY_URL", ""),
))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # No NATS, no asyncpg — reads via downstream service calls only.
    logger.info("patient-api started")
    yield
    remove_singleton(PatientServiceCoordinator)
    await http_client.aclose()
    logger.info("patient-api stopped")


app = FastAPI(lifespan=lifespan)
app.include_router(patients.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patient-api"}
