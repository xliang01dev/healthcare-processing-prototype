from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from mpi_data_provider import MpiDataProvider
from mpi_service import MpiService
import internal_router as internal

_host, _port, _db = os.getenv("POSTGRES_HOST"), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB")
data_provider = MpiDataProvider(
    reader_dsn=f"postgresql://{os.getenv('POSTGRES_READER_USER')}:{os.getenv('POSTGRES_READER_PASSWORD')}@{_host}:{_port}/{_db}",
    writer_dsn=f"postgresql://{os.getenv('POSTGRES_WRITER_USER')}:{os.getenv('POSTGRES_WRITER_PASSWORD')}@{_host}:{_port}/{_db}",
)

register_singleton(MpiService, MpiService(data_provider))


async def _handle_hydration_event(msg):
    await get_singleton(MpiService).handle_hydration_event(msg)


async def _handle_source_event(msg):
    await get_singleton(MpiService).handle_source_event(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bus = MessageBus(os.getenv("NATS_URL", ""))
    await app.state.bus.connect()

    app.state.db = data_provider
    await data_provider.connect()

    # Dedicated hydration events (add / update / remove patient records)
    await app.state.bus.subscribe("patient.hydrate", _handle_hydration_event)
    # Raw source events — handle uncorrelated patients by creating canonical IDs
    await app.state.bus.subscribe("raw.source-a", _handle_source_event)
    await app.state.bus.subscribe("raw.source-b", _handle_source_event)
    await app.state.bus.subscribe("raw.source-c", _handle_source_event)

    yield
    await app.state.bus.drain()
    remove_singleton(MpiService)
    await data_provider.disconnect()


app = FastAPI(lifespan=lifespan)
app.include_router(internal.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mpi"}
