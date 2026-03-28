from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from shared.message_bus import MessageBus
from patient_summary_service import PatientSummaryService
from patient_summary_data_provider import PatientSummaryDataProvider

service = PatientSummaryService()


async def _handle_timeline_updated(msg):
    await service.handle_timeline_updated(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bus = MessageBus(os.getenv("NATS_URL", ""))
    await app.state.bus.connect()
    await app.state.bus.subscribe("timeline.updated", _handle_timeline_updated)
    host, port, db = os.getenv("POSTGRES_HOST"), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB")
    app.state.db = PatientSummaryDataProvider(
        reader_dsn=f"postgresql://{os.getenv('POSTGRES_READER_USER')}:{os.getenv('POSTGRES_READER_PASSWORD')}@{host}:{port}/{db}",
        writer_dsn=f"postgresql://{os.getenv('POSTGRES_WRITER_USER')}:{os.getenv('POSTGRES_WRITER_PASSWORD')}@{host}:{port}/{db}",
    )
    await app.state.db.connect()
    yield
    await app.state.bus.drain()
    await app.state.db.disconnect()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patient-summary"}
