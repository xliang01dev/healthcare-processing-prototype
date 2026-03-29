import logging

from shared.message_bus import MessageBus

logger = logging.getLogger(__name__)


class IngestService:
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus

    async def ingest_event(self, source: str, body: dict) -> dict:
        logger.info("ingest_event: source=%s body=%s", source, body)
        # TODO: Assign message-id: sha256(source_id + version + source_system). See architecture Section 2.
        # TODO: Call self.bus.publish(f"raw.{source}", body).
        return {"received": True}
