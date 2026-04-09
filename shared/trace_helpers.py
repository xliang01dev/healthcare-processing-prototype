"""Helpers for OpenTelemetry trace context propagation across NATS messages."""

import json
from typing import Any, Dict
from opentelemetry.propagate import inject, extract
from opentelemetry import trace, context


def inject_trace_context(message: Dict[str, Any]) -> Dict[str, Any]:
    """Inject current trace context into a message for NATS publishing.

    Args:
        message: The message dict to send

    Returns:
        Message with _trace_context added
    """
    trace_headers = {}
    inject(trace_headers)
    return {
        **message,
        "_trace_context": trace_headers,
    }


def extract_trace_context(message: Dict[str, Any]) -> Any:
    """Extract trace context from a NATS message.

    Args:
        message: The message received from NATS

    Returns:
        OpenTelemetry context object for use in tracing
    """
    trace_context = message.get("_trace_context", {})
    return extract(trace_context)


async def trace_nats_message(
    message: Dict[str, Any],
    span_name: str,
    attributes: Dict[str, Any] | None = None,
):
    """Context manager for tracing a NATS message with propagated context.

    Usage:
        async with trace_nats_message(msg, "process_event") as span:
            span.set_attribute("patient_id", "123")
            # ... processing code

    Args:
        message: The NATS message
        span_name: Name of the span to create
        attributes: Optional attributes to set on the span
    """
    ctx = extract_trace_context(message)
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span(span_name, context=ctx) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span
