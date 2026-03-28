from shared.message_bus import MessageBus


class IngestService:
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus

    async def ingest_event(self, source: str, body: dict) -> dict:
        # TODO: Assign message-id: sha256(source_id + version + source_system). See architecture Section 2.
        # TODO: Call self.bus.publish(f"raw.{source}", body).
        print(f"[IngestService] received from {source}: {body}")
        return {"received": True}
