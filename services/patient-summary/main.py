from contextlib import asynccontextmanager
import faulthandler
import logging
import logging.config
import os
import yaml

import httpx
from fastapi import FastAPI

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from patient_summary_service import PatientSummaryService
from patient_summary_data_provider import PatientSummaryDataProvider
import internal_router as internal

faulthandler.enable()

_logging_config_file = os.getenv("LOG_CONFIG", "shared/custom-logging.yaml")
with open(_logging_config_file) as f:
    logging.config.dictConfig(yaml.safe_load(f))
logger = logging.getLogger(__name__)

_host, _port, _db = os.getenv("POSTGRES_HOST"), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB")
data_provider = PatientSummaryDataProvider(
    reader_dsn=f"postgresql://{os.getenv('POSTGRES_READER_USER')}:{os.getenv('POSTGRES_READER_PASSWORD')}@{_host}:{_port}/{_db}",
    writer_dsn=f"postgresql://{os.getenv('POSTGRES_WRITER_USER')}:{os.getenv('POSTGRES_WRITER_PASSWORD')}@{_host}:{_port}/{_db}",
)
http_client = httpx.AsyncClient()
bus = MessageBus(os.getenv("NATS_URL", ""))
register_singleton(PatientSummaryService, PatientSummaryService(
    data_provider,
    http_client,
    bus,
    timeline_url=os.getenv("TIMELINE_URL", ""),
    patient_data_url=os.getenv("PATIENT_DATA_URL", ""),
))


async def _handle_timeline_updated(msg):
    await get_singleton(PatientSummaryService).handle_timeline_updated(msg)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await bus.connect()
    await data_provider.connect()
    await bus.subscribe("timeline.updated", _handle_timeline_updated)
    logger.info("patient-summary started")
    yield
    await bus.drain()
    remove_singleton(PatientSummaryService)
    await http_client.aclose()
    await data_provider.disconnect()
    logger.info("patient-summary stopped")


app = FastAPI(lifespan=lifespan)
app.include_router(internal.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patient-summary"}
