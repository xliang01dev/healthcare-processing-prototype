class IngestService:
    async def ingest_event(self, source: str, body: dict) -> dict:
        # TODO: Assign message-id: sha256(source_id + version + source_system). See architecture Section 2.
        # TODO: Publish raw event to the message bus.
        print(f"[IngestService] received from {source}: {body}")
        return {"received": True}
