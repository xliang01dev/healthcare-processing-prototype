from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from shared.message_bus import MessageBus
import ingest_router as ingest


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bus = MessageBus(os.getenv("NATS_URL", ""))
    await app.state.bus.connect()
    yield
    await app.state.bus.drain()


app = FastAPI(lifespan=lifespan)
app.include_router(ingest.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ingestion-gateway"}
