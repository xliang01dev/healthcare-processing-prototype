from contextlib import asynccontextmanager
import faulthandler
import logging
import logging.config
import os
import yaml

from fastapi import FastAPI

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from notification_service import NotificationService

faulthandler.enable()

_logging_config_file = os.getenv("LOG_CONFIG", "shared/custom-logging.yaml")
with open(_logging_config_file) as f:
    logging.config.dictConfig(yaml.safe_load(f))
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
