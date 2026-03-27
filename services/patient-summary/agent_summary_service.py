class AgentSummaryService:
    async def handle_timeline_updated(self, msg) -> None:
        # TODO: Fetch materialized timeline from timeline.patient_timeline for the patient.
        # TODO: Build versioned prompt from timeline events and demographics.
        # TODO: Call AgentService.complete() asynchronously.
        # TODO: Deduplication write path: hash check → structural diff → cosine similarity tiebreaker.
        # TODO: Write result to llm.llm_recommendations and publish risk computed event to the message bus.
        # See architecture Section 6.
        pass

    async def run_batch(self) -> None:
        # TODO: Cron entry point — runs every 12h.
        # TODO: Query llm.llm_pending_assessments WHERE scheduled_after < NOW() AND status = 'pending'.
        # TODO: Mark each row 'processing', run assessment, mark 'done' or 'failed'.
        # TODO: On failure, enqueue to dead-letter queue (DLQ consumer not implemented in POC).
        # See architecture Section 6 batch mode steps.
        pass
