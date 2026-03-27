from contextlib import asynccontextmanager
import os

import asyncpg
from fastapi import FastAPI

from shared.message_bus import MessageBus
from agent_summary_service import AgentSummaryService

service = AgentSummaryService()


async def _handle_timeline_updated(msg):
    await service.handle_timeline_updated(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bus = MessageBus(os.getenv("NATS_URL", ""))
    await app.state.bus.connect()
    await app.state.bus.subscribe("timeline.updated", _handle_timeline_updated)
    app.state.pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    yield
    await app.state.bus.drain()
    await app.state.pool.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patient-summary"}
