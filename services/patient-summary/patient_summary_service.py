import httpx

from patient_summary_data_provider import PatientSummaryDataProvider


class PatientSummaryService:
    def __init__(self, data_provider: PatientSummaryDataProvider, http_client: httpx.AsyncClient, timeline_url: str) -> None:
        self.data_provider = data_provider
        self.http_client = http_client
        self.timeline_url = timeline_url

    async def _fetch_patient_timeline(self, canonical_patient_id: str) -> list:
        # TODO: GET {timeline_url}/internal/patient/timeline?canonical_patient_id={id}
        response = await self.http_client.get(
            f"{self.timeline_url}/internal/patient/timeline",
            params={"canonical_patient_id": canonical_patient_id},
        )
        response.raise_for_status()
        return response.json()

    async def handle_timeline_updated(self, msg) -> None:
        # TODO: Parse canonical_patient_id from msg payload.
        # TODO: Call self._fetch_patient_timeline(canonical_patient_id).
        # TODO: Build versioned prompt from timeline events and demographics.
        # TODO: Await AgenticHandler.complete(prompt, context) — block until LLM result is returned.
        # TODO: Deduplication check on result: hash check → structural diff → cosine similarity tiebreaker.
        # TODO: Call data_provider.insert_recommendation() to persist result to patient_summary.recommendations.
        # TODO: Publish risk computed event to the message bus.
        pass

    async def run_batch(self) -> None:
        # TODO: Cron entry point — batch trigger for patients whose timelines have not yet been assessed.
        # TODO: Determine candidate canonical_patient_ids (e.g. patients with no recent recommendation).
        # TODO: For each candidate: call self._fetch_patient_timeline(), then AgenticHandler.complete().
        # TODO: Write result to patient_summary.recommendations via data_provider.insert_recommendation().
        # TODO: On failure, enqueue to dead-letter queue (DLQ consumer not implemented in POC).
        pass
