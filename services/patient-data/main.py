from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from patient_data_provider import PatientDataProvider
from patient_data_service import PatientDataService
import internal_router as internal

_host, _port, _db = os.getenv("POSTGRES_HOST"), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB")
data_provider = PatientDataProvider(
    reader_dsn=f"postgresql://{os.getenv('POSTGRES_READER_USER')}:{os.getenv('POSTGRES_READER_PASSWORD')}@{_host}:{_port}/{_db}",
    writer_dsn=f"postgresql://{os.getenv('POSTGRES_WRITER_USER')}:{os.getenv('POSTGRES_WRITER_PASSWORD')}@{_host}:{_port}/{_db}",
)
bus = MessageBus(os.getenv("NATS_URL", ""))
register_singleton(PatientDataService, PatientDataService(data_provider, bus))


async def _handle_hydration_event(msg):
    await get_singleton(PatientDataService).handle_hydration_event(msg)


async def _handle_source_event(msg):
    await get_singleton(PatientDataService).handle_source_event(msg)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await bus.connect()
    await data_provider.connect()

    # Dedicated hydration events (add / update / remove patient records)
    await bus.subscribe("patient.hydrate", _handle_hydration_event)
    # Raw source events — resolve canonical_patient_id, upsert golden record, re-publish to reconcile.{canonical_patient_id}
    await bus.subscribe("raw.source-a", _handle_source_event)
    await bus.subscribe("raw.source-b", _handle_source_event)
    await bus.subscribe("raw.source-c", _handle_source_event)

    yield
    await bus.drain()
    remove_singleton(PatientDataService)
    await data_provider.disconnect()


app = FastAPI(lifespan=lifespan)
app.include_router(internal.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patient-data"}
