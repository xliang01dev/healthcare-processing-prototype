from contextlib import asynccontextmanager
import os

import asyncpg
from fastapi import FastAPI

from shared.message_bus import MessageBus
from reconciliation_service import ReconciliationService

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
    app.state.pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    yield
    await app.state.bus.drain()
    await app.state.pool.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "reconciliation"}
