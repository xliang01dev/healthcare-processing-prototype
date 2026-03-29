from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from notification_service import NotificationService

bus = MessageBus(os.getenv("NATS_URL", ""))
register_singleton(NotificationService, NotificationService(bus))


async def _handle_risk_computed(msg):
    await get_singleton(NotificationService).handle_risk_computed(msg)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await bus.connect()
    await bus.subscribe("risk.computed", _handle_risk_computed)
    yield
    await bus.drain()
    remove_singleton(NotificationService)


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "notification"}
