import logging

import httpx

from patient_summary_data_provider import PatientSummaryDataProvider
from shared.message_bus import MessageBus

logger = logging.getLogger(__name__)


class PatientSummaryService:
    def __init__(
        self,
        data_provider: PatientSummaryDataProvider,
        http_client: httpx.AsyncClient,
        bus: MessageBus,
        timeline_url: str,
        patient_data_url: str,
    ) -> None:
        self.data_provider = data_provider
        self.http_client = http_client
        self.bus = bus
        self.timeline_url = timeline_url
        self.patient_data_url = patient_data_url

    async def _fetch_patient_timeline(self, canonical_patient_id: str) -> list:
        logger.info("_fetch_patient_timeline: canonical_patient_id=%s", canonical_patient_id)
        # TODO: GET {timeline_url}/internal/patient/timeline?canonical_patient_id={id}
        response = await self.http_client.get(
            f"{self.timeline_url}/internal/patient/timeline",
            params={"canonical_patient_id": canonical_patient_id},
        )
        response.raise_for_status()
        return response.json()

    async def _fetch_golden_record(self, canonical_patient_id: str) -> dict:
        logger.info("_fetch_golden_record: canonical_patient_id=%s", canonical_patient_id)
        # TODO: GET {patient_data_url}/internal/patient/{canonical_patient_id}/golden-record
        response = await self.http_client.get(
            f"{self.patient_data_url}/internal/patient/{canonical_patient_id}/golden-record",
        )
        response.raise_for_status()
        return response.json()

    async def _assess_patient(self, canonical_patient_id: str) -> None:
        logger.info("_assess_patient: canonical_patient_id=%s", canonical_patient_id)
        # TODO: Call self._fetch_patient_timeline(canonical_patient_id).
        # TODO: Call self._fetch_golden_record(canonical_patient_id).
        # TODO: Build versioned prompt from timeline events + golden record demographics.
        # TODO: Await AgenticHandler.complete(prompt, context) — block until LLM result is returned.
        # TODO: Deduplication check on result: hash check → structural diff → cosine similarity tiebreaker.
        # TODO: Call data_provider.insert_recommendation() to persist result to patient_summary.recommendations.
        # TODO: Publish risk computed event to the message bus.

    async def fetch_latest_recommendation(self, canonical_patient_id: str) -> dict | None:
        logger.info("fetch_latest_recommendation: canonical_patient_id=%s", canonical_patient_id)
        return await self.data_provider.fetch_latest_recommendation(canonical_patient_id)

    async def fetch_recommendations(self, canonical_patient_id: str, page: int, page_size: int) -> list:
        logger.info("fetch_recommendations: canonical_patient_id=%s page=%s page_size=%s", canonical_patient_id, page, page_size)
        return await self.data_provider.fetch_recommendations(canonical_patient_id, page, page_size)

    async def run_batch_for_patient(self, canonical_patient_id: str) -> dict:
        logger.info("run_batch_for_patient: canonical_patient_id=%s", canonical_patient_id)
        # TODO: HTTP-triggered single-patient assessment — calls _assess_patient() immediately.
        await self._assess_patient(canonical_patient_id)
        return {"queued": True, "canonical_patient_id": canonical_patient_id}

    async def handle_timeline_updated(self, msg) -> None:
        logger.info("handle_timeline_updated: data=%s", msg.data)
        # TODO: Parse canonical_patient_id from msg payload.
        # TODO: Call self._assess_patient(canonical_patient_id).

    async def run_batch(self) -> None:
        logger.info("run_batch")
        # TODO: Cron entry point — batch trigger for patients whose timelines have not yet been assessed.
        # TODO: Determine candidate canonical_patient_ids (e.g. patients with no recent recommendation).
        # TODO: For each candidate: call self._assess_patient(canonical_patient_id).
        # TODO: On failure, enqueue to dead-letter queue (DLQ consumer not implemented in POC).
