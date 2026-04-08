"""Prometheus metrics endpoint router for FastAPI services."""

from fastapi import APIRouter
from prometheus_client import REGISTRY, generate_latest, CollectorRegistry
from prometheus_client import Counter, Histogram, Gauge
import time
from typing import Callable
from fastapi.responses import Response

# Create a registry for this service
_registry = REGISTRY

# Define standard metrics
request_count = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"],
    registry=_registry,
)

request_duration = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=_registry,
)

# Health gauge (1 = healthy, 0 = unhealthy)
service_health = Gauge(
    "service_health",
    "Service health status (1=healthy, 0=unhealthy)",
    registry=_registry,
)

# Initialize as healthy
service_health.set(1)


def create_metrics_router() -> APIRouter:
    """Create and return a metrics router."""
    router = APIRouter()

    @router.get("/metrics")
    async def metrics():
        """Expose Prometheus metrics without _created timestamp metrics.

        The _created metrics are auto-generated Unix timestamps that clutter
        dashboards and aren't useful for application-level monitoring.
        """
        metrics_output = generate_latest(_registry).decode('utf-8')
        # Filter out _created metrics (Unix timestamps that confuse Grafana)
        lines = [
            line for line in metrics_output.split('\n')
            if line and '_created' not in line
        ]
        filtered = '\n'.join(lines).encode('utf-8')

        return Response(
            content=filtered,
            media_type="text/plain; charset=utf-8",
        )

    return router


async def record_request(
    method: str,
    endpoint: str,
    status_code: int,
    duration: float,
) -> None:
    """Record HTTP request metrics."""
    request_count.labels(method=method, endpoint=endpoint, status=status_code).inc()
    request_duration.labels(method=method, endpoint=endpoint).observe(duration)
