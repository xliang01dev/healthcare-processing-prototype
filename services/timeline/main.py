from contextlib import asynccontextmanager
import os

import asyncpg
from fastapi import FastAPI

from shared.message_bus import MessageBus
from timeline_service import TimelineService

service = TimelineService()


async def _handle_reconciled_event(msg):
    await service.handle_reconciled_event(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bus = MessageBus(os.getenv("NATS_URL", ""))
    await app.state.bus.connect()
    await app.state.bus.subscribe("reconciled.events", _handle_reconciled_event)
    app.state.pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    yield
    await app.state.bus.drain()
    await app.state.pool.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "timeline"}
