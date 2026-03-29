from contextlib import asynccontextmanager
import logging
import os

from fastapi import FastAPI

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from notification_service import NotificationService

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

bus = MessageBus(os.getenv("NATS_URL", ""))
register_singleton(NotificationService, NotificationService(bus))


async def _handle_risk_computed(msg):
    await get_singleton(NotificationService).handle_risk_computed(msg)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await bus.connect()
    await bus.subscribe("risk.computed", _handle_risk_computed)
    logger.info("notification started")
    yield
    await bus.drain()
    remove_singleton(NotificationService)
    logger.info("notification stopped")


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "notification"}
