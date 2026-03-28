from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from ingest_service import IngestService
import ingest_router as ingest

bus = MessageBus(os.getenv("NATS_URL", ""))
register_singleton(IngestService, IngestService(bus))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await bus.connect()

    yield
    await bus.drain()
    remove_singleton(IngestService)


app = FastAPI(lifespan=lifespan)
app.include_router(ingest.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ingestion-gateway"}
