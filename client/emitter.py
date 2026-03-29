"""
NATS connection and publish wrapper for the terminal client.

Connects directly to NATS (bypassing the Ingestion Gateway) so the client
can publish to any topic — including patient.hydrate which the gateway does
not expose as an HTTP endpoint.
"""

import json

import nats
import nats.errors


class Emitter:
    def __init__(self, url: str) -> None:
        self._url = url
        self._nc = None

    async def connect(self) -> None:
        self._nc = await nats.connect(
            self._url,
            connect_timeout=3,
            max_reconnect_attempts=0,   # fail fast — do not retry silently
        )

    async def publish(self, subject: str, payload: dict) -> None:
        assert self._nc is not None, "Emitter not connected"
        data = json.dumps(payload, default=str).encode()
        await self._nc.publish(subject, data)
        try:
            await self._nc.flush()
        except nats.errors.UnexpectedEOF:
            # Connection may have been closed, but publish was queued
            pass

    async def close(self) -> None:
        if self._nc is not None:
            await self._nc.drain()
            self._nc = None

    @property
    def connected(self) -> bool:
        return self._nc is not None and not self._nc.is_closed
