from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from shared.message_bus import MessageBus
from notification_service import NotificationService

service = NotificationService()


async def _handle_risk_computed(msg):
    await service.handle_risk_computed(msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.bus = MessageBus(os.getenv("NATS_URL", ""))
    await app.state.bus.connect()
    await app.state.bus.subscribe("risk.computed", _handle_risk_computed)
    yield
    await app.state.bus.drain()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "notification"}
