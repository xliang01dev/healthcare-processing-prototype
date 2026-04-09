from contextlib import asynccontextmanager
import faulthandler
import logging
import logging.config
import json
import os
import yaml

from fastapi import FastAPI

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from shared.metrics_router import create_metrics_router
from shared.metrics_middleware import MetricsMiddleware
from shared.opentelemetry_config import init_tracing, get_tracer
from shared.trace_helpers import extract_trace_context
from timeline_service import TimelineService
from timeline_data_provider import TimelineDataProvider
import internal_router as internal

faulthandler.enable()

_logging_config_file = os.getenv("LOG_CONFIG", "shared/custom-logging.yaml")
with open(_logging_config_file) as f:
    logging.config.dictConfig(yaml.safe_load(f))
logger = logging.getLogger(__name__)

# Initialize OpenTelemetry tracing
init_tracing("patient-timeline")
tracer = get_tracer(__name__)

_host, _port, _db = os.getenv("POSTGRES_HOST"), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB")
data_provider = TimelineDataProvider(
    reader_dsn=f"postgresql://{os.getenv('POSTGRES_READER_USER')}:{os.getenv('POSTGRES_READER_PASSWORD')}@{_host}:{_port}/{_db}",
    writer_dsn=f"postgresql://{os.getenv('POSTGRES_WRITER_USER')}:{os.getenv('POSTGRES_WRITER_PASSWORD')}@{_host}:{_port}/{_db}",
    pool_min_size=int(os.getenv("POSTGRES_POOL_MIN_SIZE", "2")),
    pool_max_size=int(os.getenv("POSTGRES_POOL_MAX_SIZE", "5")),
)
bus = MessageBus(os.getenv("NATS_URL", ""))
register_singleton(TimelineService, TimelineService(data_provider, bus))


async def _handle_reconciled_event(msg):
    """Handle reconciled event with trace context propagation."""
    payload = json.loads(msg.data.decode())
    ctx = extract_trace_context(payload)

    with tracer.start_as_current_span("handle_reconciled_event", context=ctx) as span:
        span.set_attribute("event_type", payload.get("event_type"))
        await get_singleton(TimelineService).handle_reconciled_event(payload)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await bus.connect()
    await data_provider.connect()
    await bus.subscribe("reconciled.events", _handle_reconciled_event)
    logger.info("patient-timeline started")
    yield
    await bus.drain()
    remove_singleton(TimelineService)
    await data_provider.disconnect()
    logger.info("patient-timeline stopped")


app = FastAPI(lifespan=lifespan)
app.add_middleware(MetricsMiddleware)
app.include_router(internal.router)
app.include_router(create_metrics_router())


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patient-timeline"}
