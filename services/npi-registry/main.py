from contextlib import asynccontextmanager
import faulthandler
import logging
import logging.config
import os
import yaml

from fastapi import FastAPI

from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from npi_service import NPIRegistryService
from npi_data_provider import NPIDataProvider
import npi_router

faulthandler.enable()

_logging_config_file = os.getenv("LOG_CONFIG", "shared/custom-logging.yaml")
with open(_logging_config_file) as f:
    logging.config.dictConfig(yaml.safe_load(f))
logger = logging.getLogger(__name__)

_host, _port, _db = os.getenv("POSTGRES_HOST", ""), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB", "")
data_provider = NPIDataProvider(
    reader_dsn=f"postgresql://{os.getenv('POSTGRES_READER_USER', '')}:{os.getenv('POSTGRES_READER_PASSWORD', '')}@{_host}:{_port}/{_db}",
    writer_dsn=f"postgresql://{os.getenv('POSTGRES_WRITER_USER', '')}:{os.getenv('POSTGRES_WRITER_PASSWORD', '')}@{_host}:{_port}/{_db}",
)
register_singleton(NPIRegistryService, NPIRegistryService(data_provider))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await data_provider.connect()
    logger.info("npi-registry started")
    yield
    await data_provider.disconnect()
    remove_singleton(NPIRegistryService)
    logger.info("npi-registry stopped")


app = FastAPI(lifespan=lifespan)
app.include_router(npi_router.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "npi-registry"}
