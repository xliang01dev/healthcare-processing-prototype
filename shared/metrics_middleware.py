"""Middleware for automatic Prometheus metrics collection."""

import re
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from shared.metrics_router import record_request

logger = logging.getLogger(__name__)


def _normalize_endpoint(path: str) -> str:
    """Normalize endpoint path by replacing IDs with placeholders.

    Strategy: Replace segments that look like IDs (UUIDs, long alphanumeric strings)
    while preserving known API keywords.

    Examples:
    - /patient/550e8400-e29b-41d4-a716-446655440000/recommendation -> /patient/{id}/recommendation
    - /patient/medicare/12345678/timeline -> /patient/medicare/{id}/timeline
    - /patient/canonical_id/some-long-id/rec -> /patient/canonical_id/{id}/rec
    """
    # Keywords that should be preserved (API path segments, not IDs)
    preserved_keywords = {
        'patient', 'medicare', 'canonical_id', 'internal', 'resolve',
        'recommendation', 'timeline', 'metrics', 'health', 'ingest',
        'hydrate', 'reconcile', 'api', 'v1', 'v2'
    }

    # Replace UUID patterns (8-4-4-4-12 hex digits)
    path = re.sub(r'[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}', '{id}', path, flags=re.IGNORECASE)

    # Replace numeric IDs (any sequence of digits)
    path = re.sub(r'/\d+(?=/|$)', '/{id}', path)

    # Replace long alphanumeric segments (8+ chars) that aren't known keywords
    def replace_long_segment(match):
        segment = match.group(1)
        if segment.lower() not in preserved_keywords and len(segment) >= 8:
            return '/{id}'
        return f'/{segment}'

    path = re.sub(r'/([a-zA-Z0-9_-]+)', replace_long_segment, path)

    return path


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware that records HTTP request metrics for Prometheus."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request and record metrics."""
        # Skip metrics endpoint to avoid recursion
        if request.url.path == "/metrics":
            return await call_next(request)

        start_time = time.time()
        method = request.method
        endpoint = _normalize_endpoint(request.url.path)

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            # Extract status code from exception (HTTP exceptions have status_code, others default to 500)
            duration = time.time() - start_time
            status_code = getattr(exc, "status_code", 500)
            await record_request(method, endpoint, status_code, duration)
            raise

        duration = time.time() - start_time
        await record_request(method, endpoint, status_code, duration)

        return response
