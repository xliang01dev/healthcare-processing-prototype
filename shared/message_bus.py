import json
import nats

from typing import Any
from nats.aio.client import Client as NATS

class MessageBus:
    """
    Messaging abstraction supporting both NATS core pub/sub and JetStream streams.

    Core Pub/Sub (fire-and-forget):
    - publish(topic, payload): Publish to pub/sub topic
    - subscribe(topic, handler): Subscribe to pub/sub topic (auto-ack)

    JetStream Streams (durable, with acknowledgment):
    - publish_stream(topic, payload): Publish to stream (returns sequence)
    - subscribe_stream(topic, handler, durable_name, deliver_group): Subscribe to stream consumer group
    """

    def __init__(self, url: str) -> None:
        self._url = url
        self._nc: NATS | None = None

    async def connect(self) -> None:
        if not self._url:
            raise ValueError("MessageBus requires a NATS URL — set the NATS_URL environment variable")
        self._nc = await nats.connect(self._url)

    async def publish(self, topic: str, payload: dict) -> None:
        """Publish to NATS core pub/sub topic (fire-and-forget, no persistence)."""
        assert self._nc is not None, "MessageBus not connected — call connect() first"
        await self._nc.publish(topic, json.dumps(payload).encode())

    async def publish_stream(self, topic: str, payload: dict) -> dict:
        """Publish to JetStream stream (durable, with sequence tracking).

        Returns PublishAck metadata: {'stream': str, 'sequence': int}
        """
        assert self._nc is not None, "MessageBus not connected — call connect() first"
        js = self._nc.jetstream()
        pub_ack = await js.publish(topic, json.dumps(payload).encode())
        return {
            "stream": pub_ack.stream,
            "sequence": pub_ack.sequence
        }

    async def subscribe(self, topic: str, handler: Any) -> None:
        """Subscribe to NATS core pub/sub topic (fire-and-forget, no durable state)."""
        assert self._nc is not None, "MessageBus not connected — call connect() first"
        await self._nc.subscribe(topic, cb=handler)

    async def subscribe_stream(
        self,
        topic: str,
        handler: Any,
        durable_name: str,
        deliver_group: str
    ) -> Any:
        """Subscribe to JetStream stream with consumer group (durable, with acknowledgment).

        Args:
            topic: Stream subject (e.g., "reconciliation.tasks")
            handler: Async callback function that receives message
            durable_name: Unique identifier per instance (e.g., "worker-1", "worker-2")
            deliver_group: Shared group name for round-robin (e.g., "reconciliation-workers")

        Returns:
            JetStream consumer subscription (caller handles msg.ack()/msg.nak())

        Example:
            # All workers use same deliver_group but unique durable_name per instance
            await bus.subscribe_stream(
                topic="reconciliation.tasks",
                handler=process_task,
                durable_name="worker-1",                    # Unique per instance
                deliver_group="reconciliation-workers"      # Same for all workers
            )
        """
        assert self._nc is not None, "MessageBus not connected — call connect() first"
        js = self._nc.jetstream()

        # Create or get existing consumer
        consumer = await js.subscribe(
            subject=topic,
            cb=handler,
            durable_name=durable_name,
            deliver_group=deliver_group
        )
        return consumer

    async def flush(self) -> None:
        assert self._nc is not None, "MessageBus not connected — call connect() first"
        await self._nc.flush()

    async def drain(self) -> None:
        if self._nc is not None:
            await self._nc.drain()
