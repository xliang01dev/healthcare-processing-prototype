from contextlib import asynccontextmanager
import os

import httpx
from fastapi import FastAPI

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from patient_summary_service import PatientSummaryService
from patient_summary_data_provider import PatientSummaryDataProvider

_host, _port, _db = os.getenv("POSTGRES_HOST"), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB")
data_provider = PatientSummaryDataProvider(
    reader_dsn=f"postgresql://{os.getenv('POSTGRES_READER_USER')}:{os.getenv('POSTGRES_READER_PASSWORD')}@{_host}:{_port}/{_db}",
    writer_dsn=f"postgresql://{os.getenv('POSTGRES_WRITER_USER')}:{os.getenv('POSTGRES_WRITER_PASSWORD')}@{_host}:{_port}/{_db}",
)
http_client = httpx.AsyncClient()

register_singleton(PatientSummaryService, PatientSummaryService(data_provider, http_client, os.getenv("TIMELINE_URL", "")))


async def _handle_timeline_updated(msg):
    await get_singleton(PatientSummaryService).handle_timeline_updated(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bus = MessageBus(os.getenv("NATS_URL", ""))
    await app.state.bus.connect()
    await app.state.bus.subscribe("timeline.updated", _handle_timeline_updated)
    app.state.db = data_provider
    await data_provider.connect()
    yield
    await app.state.bus.drain()
    remove_singleton(PatientSummaryService)
    await http_client.aclose()
    await data_provider.disconnect()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patient-summary"}
