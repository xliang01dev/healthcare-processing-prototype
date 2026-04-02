from contextlib import asynccontextmanager
import faulthandler
import logging
import logging.config
import os
import yaml

import httpx
from fastapi import FastAPI

from shared.singleton_store import register_singleton, remove_singleton
from patient_coordinator_service import PatientCoordinatorService
from internal_router import router

faulthandler.enable()

_logging_config_file = os.getenv("LOG_CONFIG", "shared/custom-logging.yaml")
with open(_logging_config_file) as f:
    logging.config.dictConfig(yaml.safe_load(f))
logger = logging.getLogger(__name__)

http_client = httpx.AsyncClient()
register_singleton(PatientCoordinatorService, PatientCoordinatorService(
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
    remove_singleton(PatientCoordinatorService)
    await http_client.aclose()
    logger.info("patient-api stopped")


app = FastAPI(lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patient-api"}
