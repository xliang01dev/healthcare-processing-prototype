from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from shared.message_bus import MessageBus
from mpi_data_provider import MpiDataProvider
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
    host, port, db = os.getenv("POSTGRES_HOST"), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB")
    app.state.db = MpiDataProvider(
        reader_dsn=f"postgresql://{os.getenv('POSTGRES_READER_USER')}:{os.getenv('POSTGRES_READER_PASSWORD')}@{host}:{port}/{db}",
        writer_dsn=f"postgresql://{os.getenv('POSTGRES_WRITER_USER')}:{os.getenv('POSTGRES_WRITER_PASSWORD')}@{host}:{port}/{db}",
    )
    await app.state.db.connect()
    yield
    await app.state.bus.drain()
    await app.state.db.disconnect()


app = FastAPI(lifespan=lifespan)
app.include_router(internal.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mpi"}
