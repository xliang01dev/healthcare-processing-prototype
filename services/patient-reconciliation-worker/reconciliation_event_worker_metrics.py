"""Prometheus metrics for reconciliation event processing."""

from prometheus_client import Histogram, Counter, Gauge
from prometheus_client import REGISTRY

# Processing duration for reconciliation tasks
reconciliation_duration = Histogram(
    "reconciliation_task_duration_seconds",
    "Time to process a reconciliation task",
    ["status"],  # success, failure
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
    registry=REGISTRY,
)

# Total reconciliation tasks processed
reconciliation_total = Counter(
    "reconciliation_tasks_total",
    "Total reconciliation tasks processed",
    ["status"],  # success, failure
    registry=REGISTRY,
)

# Reconciliation tasks currently being processed
reconciliation_in_flight = Gauge(
    "reconciliation_tasks_in_flight",
    "Reconciliation tasks currently being processed",
    registry=REGISTRY,
)
