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
from patient_data_provider import PatientDataProvider
from patient_data_service import PatientDataService
import internal_router as internal

faulthandler.enable()

_logging_config_file = os.getenv("LOG_CONFIG", "shared/custom-logging.yaml")
with open(_logging_config_file) as f:
    logging.config.dictConfig(yaml.safe_load(f))
logger = logging.getLogger(__name__)

# Initialize OpenTelemetry tracing
init_tracing("patient-data")
tracer = get_tracer(__name__)

_host, _port, _db = os.getenv("POSTGRES_HOST"), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB")
data_provider = PatientDataProvider(
    reader_dsn=f"postgresql://{os.getenv('POSTGRES_READER_USER')}:{os.getenv('POSTGRES_READER_PASSWORD')}@{_host}:{_port}/{_db}",
    writer_dsn=f"postgresql://{os.getenv('POSTGRES_WRITER_USER')}:{os.getenv('POSTGRES_WRITER_PASSWORD')}@{_host}:{_port}/{_db}",
    pool_min_size=int(os.getenv("POSTGRES_POOL_MIN_SIZE", "2")),
    pool_max_size=int(os.getenv("POSTGRES_POOL_MAX_SIZE", "5")),
)
bus = MessageBus(os.getenv("NATS_URL", ""))
register_singleton(PatientDataService, PatientDataService(data_provider, bus))


async def _handle_hydration_event(msg):
    """Handle hydration event with trace context propagation."""
    payload = json.loads(msg.data.decode())
    ctx = extract_trace_context(payload)

    with tracer.start_as_current_span("handle_hydration_event", context=ctx) as span:
        span.set_attribute("medicare_id", payload.get("medicare_id"))
        logger.info(f"_handle_hydration_event called with msg={payload}")
        try:
            await get_singleton(PatientDataService).handle_hydration_event(payload)
        except Exception as e:
            span.set_attribute("error", True)
            logger.error(f"Exception in _handle_hydration_event: {e}", exc_info=True)
            raise


async def _handle_source_event(msg):
    """Handle source event with trace context propagation."""
    payload = json.loads(msg.data.decode())
    ctx = extract_trace_context(payload)

    with tracer.start_as_current_span("handle_source_event", context=ctx) as span:
        span.set_attribute("source", payload.get("source"))
        span.set_attribute("event_type", payload.get("event_type"))
        try:
            await get_singleton(PatientDataService).handle_source_event(payload)
        except Exception as e:
            span.set_attribute("error", True)
            raise


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await bus.connect()
    await bus.ensure_stream("RECONCILE", ["reconcile"])
    await data_provider.connect()
    logger.info("lifespan: data provider connected")

    # Dedicated hydration events (add / update / remove patient records)
    await bus.subscribe("patient.hydrate", _handle_hydration_event)
    logger.info("lifespan: subscribed to patient.hydrate")

    # Raw source events — resolve canonical_patient_id, upsert golden record, re-publish to reconcile.{canonical_patient_id}
    await bus.subscribe("raw.source-medicare", _handle_source_event)
    await bus.subscribe("raw.source-hospital", _handle_source_event)
    await bus.subscribe("raw.source-labs", _handle_source_event)
    logger.info("lifespan: subscribed to source events")

    logger.info("patient-data started")
    yield

    await bus.drain()
    remove_singleton(PatientDataService)
    await data_provider.disconnect()
    logger.info("patient-data stopped")


app = FastAPI(lifespan=lifespan)
app.add_middleware(MetricsMiddleware)
app.include_router(internal.router)
app.include_router(create_metrics_router())


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patient-data"}
