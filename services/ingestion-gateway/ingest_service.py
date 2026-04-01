import logging

from shared.message_bus import MessageBus

logger = logging.getLogger(__name__)


class IngestService:
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus

    async def ingest_event(self, source: str, body: dict) -> dict:
        logger.info("ingest_event: source=%s body=%s", source, body)
        await self.bus.publish(
            topic=f"raw.{source}",
            payload=body
        )
        return {"received": True}

    async def hydrate_patient(self, body: dict) -> dict:
        logger.info("hydrate_patient: body=%s", body)
        await self.bus.publish(
            topic="patient.hydrate",
            payload=body
        )
        return {"received": True}
