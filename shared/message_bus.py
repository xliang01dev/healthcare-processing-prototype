import json

import nats


class MessageBus:
    """
    Pub/sub abstraction backed by NATS core.
    Swap the backing implementation (JetStream, Kafka) without touching service logic.
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._nc = None

    async def connect(self) -> None:
        if not self._url:
            raise ValueError("MessageBus requires a NATS URL — set the NATS_URL environment variable")
        self._nc = await nats.connect(self._url)

    async def publish(self, topic: str, payload: dict) -> None:
        assert self._nc is not None, "MessageBus not connected — call connect() first"
        await self._nc.publish(topic, json.dumps(payload).encode())

    async def subscribe(self, topic: str, handler) -> None:
        assert self._nc is not None, "MessageBus not connected — call connect() first"
        await self._nc.subscribe(topic, cb=handler)

    async def drain(self) -> None:
        if self._nc is not None:
            await self._nc.drain()
