"""OpenTelemetry initialization and configuration for all services."""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor


def init_tracing(service_name: str) -> None:
    """Initialize OpenTelemetry tracing for a service.

    Sets up:
    - OTLP exporter (sends traces to Jaeger via HTTP)
    - FastAPI instrumentation (auto-traces HTTP endpoints)
    - httpx instrumentation (auto-traces HTTP client calls)
    - Trace context propagation

    Args:
        service_name: The name of the service (e.g., "patient-data", "ingestion-gateway")
    """
    # Get Jaeger OTLP receiver endpoint from environment
    # Note: Inside Docker, use internal port 4318 (OTLP HTTP collector)
    # External port 3032 maps to internal 4318
    jaeger_host = os.getenv("JAEGER_HOST", "jaeger")
    jaeger_port = os.getenv("JAEGER_PORT", "4318")
    otlp_endpoint = f"http://{jaeger_host}:{jaeger_port}/v1/traces"

    # Create OTLP exporter (sends spans to Jaeger via HTTP)
    otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint)

    # Create resource with service name
    resource = Resource(attributes={"service.name": service_name})

    # Create tracer provider with resource
    trace_provider = TracerProvider(resource=resource)

    # Add batch processor (batches spans for efficiency)
    trace_provider.add_span_processor(
        BatchSpanProcessor(otlp_exporter)
    )

    # Set as global tracer provider
    trace.set_tracer_provider(trace_provider)

    # Auto-instrument FastAPI (traces HTTP endpoints)
    FastAPIInstrumentor().instrument()

    # Auto-instrument httpx (traces HTTP client requests)
    HTTPXClientInstrumentor().instrument()


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance for a module.

    Usage:
        tracer = get_tracer(__name__)
        with tracer.start_as_current_span("operation"):
            # ... code to trace

    Args:
        name: Module name (typically __name__)

    Returns:
        OpenTelemetry Tracer instance
    """
    return trace.get_tracer(name)
