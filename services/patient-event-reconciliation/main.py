from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from patient_event_reconciliation_service import PatientEventReconciliationService
from patient_event_reconciliation_data_provider import PatientEventReconciliationDataProvider
import internal_router as internal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_host, _port, _db = os.getenv("POSTGRES_HOST"), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB")
data_provider = PatientEventReconciliationDataProvider(
    reader_dsn=f"postgresql://{os.getenv('POSTGRES_READER_USER')}:{os.getenv('POSTGRES_READER_PASSWORD')}@{_host}:{_port}/{_db}",
    writer_dsn=f"postgresql://{os.getenv('POSTGRES_WRITER_USER')}:{os.getenv('POSTGRES_WRITER_PASSWORD')}@{_host}:{_port}/{_db}",
)
bus = MessageBus(os.getenv("NATS_URL", ""))
register_singleton(PatientEventReconciliationService, PatientEventReconciliationService(data_provider, bus))


async def _handle_reconcile_event(msg):
    await get_singleton(PatientEventReconciliationService).handle_reconcile_event(msg)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await bus.connect()
    await data_provider.connect()
    # Patient data service publishes to reconcile.{canonical_patient_id} — wildcard subscription preserves per-patient ordering
    await bus.subscribe("reconcile.*", _handle_reconcile_event)
    logger.info("patient-event-reconciliation started")
    yield
    await bus.drain()
    remove_singleton(PatientEventReconciliationService)
    await data_provider.disconnect()
    logger.info("patient-event-reconciliation stopped")


app = FastAPI(lifespan=lifespan)
app.include_router(internal.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patient-event-reconciliation"}
