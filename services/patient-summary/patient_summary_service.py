class PatientSummaryService:
    async def handle_timeline_updated(self, msg) -> None:
        # TODO: Parse canonical_patient_id from msg payload.
        # TODO: Fetch materialized timeline from timeline.patient_timeline via data provider.
        # TODO: Build versioned prompt from timeline events and demographics.
        # TODO: Await AgenticHandler.complete(prompt, context) — block until LLM result is returned.
        # TODO: Deduplication check on result: hash check → structural diff → cosine similarity tiebreaker.
        # TODO: Call data_provider.insert_recommendation() to persist result to patient_summary.recommendations.
        # TODO: Publish risk computed event to the message bus.
        # See architecture Section 6.
        pass

    async def run_batch(self) -> None:
        # TODO: Cron entry point — runs every 12h.
        # TODO: Query timeline.pending_processing WHERE scheduled_after < NOW() AND status = 'pending'.
        #   Note: timeline.pending_processing is owned by the timeline service (debounce state).
        #   Patient summary reads it here only to drive batch LLM assessments.
        # TODO: For each due row: call AgenticHandler.complete(), write result to patient_summary.recommendations.
        # TODO: On failure, enqueue to dead-letter queue (DLQ consumer not implemented in POC).
        # See architecture Section 6 batch mode steps.
        pass
