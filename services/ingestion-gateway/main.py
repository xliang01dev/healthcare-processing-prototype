from contextlib import asynccontextmanager
import faulthandler
import logging
import logging.config
import os
import yaml

from fastapi import FastAPI

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from ingest_service import IngestService
import ingest_router as ingest

faulthandler.enable()

_logging_config_file = os.getenv("LOG_CONFIG", "shared/custom-logging.yaml")
with open(_logging_config_file) as f:
    logging.config.dictConfig(yaml.safe_load(f))
logger = logging.getLogger(__name__)

# logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s", force=True)
# logger = logging.getLogger(__name__)

bus = MessageBus(os.getenv("NATS_URL", ""))
register_singleton(IngestService, IngestService(bus))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await bus.connect()
    logger.info("ingestion-gateway started")
    yield
    await bus.drain()
    remove_singleton(IngestService)
    logger.info("ingestion-gateway stopped")


app = FastAPI(lifespan=lifespan)
app.include_router(ingest.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ingestion-gateway"}
