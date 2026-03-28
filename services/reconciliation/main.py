from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from reconciliation_service import ReconciliationService
from reconciliation_data_provider import ReconciliationDataProvider

_host, _port, _db = os.getenv("POSTGRES_HOST"), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB")
data_provider = ReconciliationDataProvider(
    reader_dsn=f"postgresql://{os.getenv('POSTGRES_READER_USER')}:{os.getenv('POSTGRES_READER_PASSWORD')}@{_host}:{_port}/{_db}",
    writer_dsn=f"postgresql://{os.getenv('POSTGRES_WRITER_USER')}:{os.getenv('POSTGRES_WRITER_PASSWORD')}@{_host}:{_port}/{_db}",
)

register_singleton(ReconciliationService, ReconciliationService(data_provider))


async def _handle_raw_event(msg):
    await get_singleton(ReconciliationService).handle_raw_event(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bus = MessageBus(os.getenv("NATS_URL", ""))
    await app.state.bus.connect()
    await app.state.bus.subscribe("raw.source-a", _handle_raw_event)
    await app.state.bus.subscribe("raw.source-b", _handle_raw_event)
    await app.state.bus.subscribe("raw.source-c", _handle_raw_event)
    app.state.db = data_provider
    await data_provider.connect()
    yield
    await app.state.bus.drain()
    remove_singleton(ReconciliationService)
    await data_provider.disconnect()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "reconciliation"}
