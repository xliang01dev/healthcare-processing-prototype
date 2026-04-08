from contextlib import asynccontextmanager
import faulthandler
import logging
import logging.config
import os
import yaml

from fastapi import FastAPI

# Debugpy setup for VSCode remote attach
if os.getenv("INCLUDE_DEBUG", "false").lower() == "debugpy":
    import debugpy
    debugpy.listen(("0.0.0.0", 5678))

from shared.message_bus import MessageBus
from shared.singleton_store import get_singleton, register_singleton, remove_singleton
from shared.metrics_router import create_metrics_router
from shared.metrics_middleware import MetricsMiddleware
from patient_event_reconciliation_service import PatientEventReconciliationService
from patient_event_reconciliation_data_provider import PatientEventReconciliationDataProvider
import internal_router as internal

faulthandler.enable()

_logging_config_file = os.getenv("LOG_CONFIG", "shared/custom-logging.yaml")
with open(_logging_config_file) as f:
    logging.config.dictConfig(yaml.safe_load(f))
logger = logging.getLogger(__name__)

_host, _port, _db = os.getenv("POSTGRES_HOST"), os.getenv("POSTGRES_PORT", "5432"), os.getenv("POSTGRES_DB")
_worker_id = os.getenv("WORKER_ID", "reconciliation-service-default")
data_provider = PatientEventReconciliationDataProvider(
    reader_dsn=f"postgresql://{os.getenv('POSTGRES_READER_USER')}:{os.getenv('POSTGRES_READER_PASSWORD')}@{_host}:{_port}/{_db}",
    writer_dsn=f"postgresql://{os.getenv('POSTGRES_WRITER_USER')}:{os.getenv('POSTGRES_WRITER_PASSWORD')}@{_host}:{_port}/{_db}",
    pool_min_size=int(os.getenv("POSTGRES_POOL_MIN_SIZE", "2")),
    pool_max_size=int(os.getenv("POSTGRES_POOL_MAX_SIZE", "5")),
)
bus = MessageBus(os.getenv("NATS_URL", ""))

register_singleton(PatientEventReconciliationService, PatientEventReconciliationService(data_provider, bus))


async def _handle_reconcile_event(msg):
    await get_singleton(PatientEventReconciliationService).handle_reconcile_event(msg)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await bus.connect()
    await bus.ensure_stream("RECONCILE", ["reconcile"])
    await bus.ensure_stream("RECONCILIATION_TASKS", ["reconciliation.tasks"])
    await data_provider.connect()
    # Patient data service publishes to reconcile stream — subscribe with queue group for round-robin distribution
    await bus.subscribe_stream("reconcile", _handle_reconcile_event, service_name=_worker_id, message_group="reconciliation-workers")
    logger.info("patient-event-reconciliation started")
    yield
    await bus.drain()
    remove_singleton(PatientEventReconciliationService)
    await data_provider.disconnect()
    logger.info("patient-event-reconciliation stopped")


app = FastAPI(lifespan=lifespan)
app.add_middleware(MetricsMiddleware)
app.include_router(internal.router)
app.include_router(create_metrics_router())


@app.get("/health")
async def health():
    return {"status": "ok", "service": "patient-event-reconciliation"}
