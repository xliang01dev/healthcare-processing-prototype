from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from shared.message_bus import MessageBus
from reconciliation_service import ReconciliationService
from reconciliation_data_provider import ReconciliationDataProvider

service = ReconciliationService()


async def _handle_raw_event(msg):
    await service.handle_raw_event(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bus = MessageBus(os.getenv("NATS_URL", ""))
    await app.state.bus.connect()
    await app.state.bus.subscribe("raw.source-a", _handle_raw_event)
    await app.state.bus.subscribe("raw.source-b", _handle_raw_event)
    await app.state.bus.subscribe("raw.source-c", _handle_raw_event)
    host, port, db = os.getenv("POSTGRES_HOST"), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB")
    app.state.db = ReconciliationDataProvider(
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
    return {"status": "ok", "service": "reconciliation"}
