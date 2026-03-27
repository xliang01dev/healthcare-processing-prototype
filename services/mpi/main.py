from contextlib import asynccontextmanager
import os

import asyncpg
from fastapi import FastAPI

from shared.message_bus import MessageBus
import internal_router as internal


async def _noop_handler(msg):
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bus = MessageBus(os.getenv("NATS_URL", ""))
    await app.state.bus.connect()
    await app.state.bus.subscribe("raw.source-a", _noop_handler)
    await app.state.bus.subscribe("raw.source-b", _noop_handler)
    await app.state.bus.subscribe("raw.source-c", _noop_handler)
    app.state.pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    yield
    await app.state.bus.drain()
    await app.state.pool.close()


app = FastAPI(lifespan=lifespan)
app.include_router(internal.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mpi"}
