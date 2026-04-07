import logging
import json
import httpx

from shared.message_bus import MessageBus
from shared.event_models import PatientTimeline, ReconciledEvent

from patient_summary_data_provider import PatientSummaryDataProvider
from patient_summary_models import PatientRecommendation
from agentic_handler import AgenticHandler

logger = logging.getLogger(__name__)


class PatientSummaryService:
    def __init__(
        self,
        data_provider: PatientSummaryDataProvider,
        agentic_handler: AgenticHandler,
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
        self.agentic_handler = agentic_handler

    async def _fetch_patient_timeline_latest(self, canonical_patient_id: str) -> PatientTimeline:
        logger.info("_fetch_patient_timeline_latest: canonical_patient_id=%s", canonical_patient_id)
        response = await self.http_client.get(
            f"{self.timeline_url}/internal/patient/timeline/latest",
            params={"canonical_patient_id": canonical_patient_id},
        )
        response.raise_for_status()
        timeline_json = response.json()
        return PatientTimeline.model_validate(timeline_json)

    async def _fetch_golden_record(self, canonical_patient_id: str) -> dict:
        logger.info("_fetch_golden_record: canonical_patient_id=%s", canonical_patient_id)
        # TODO: GET {patient_data_url}/internal/patient/{canonical_patient_id}/golden-record
        response = await self.http_client.get(
            f"{self.patient_data_url}/internal/patient/{canonical_patient_id}/golden-record",
        )
        response.raise_for_status()
        return response.json()

    async def fetch_latest_recommendation(self, canonical_patient_id: str) -> dict | None:
        logger.info("fetch_latest_recommendation: canonical_patient_id=%s", canonical_patient_id)
        return await self.data_provider.fetch_latest_recommendation(canonical_patient_id)

    async def fetch_recommendations(self, canonical_patient_id: str, page: int, page_size: int) -> list:
        logger.info("fetch_recommendations: canonical_patient_id=%s page=%s page_size=%s", canonical_patient_id, page, page_size)
        return await self.data_provider.fetch_recommendations(canonical_patient_id, page, page_size)

    async def handle_timeline_updated(self, msg) -> None:
        reconciled_event_json = json.loads(msg.data.decode())
        reconciled_event = ReconciledEvent.model_validate_json(reconciled_event_json)

        canonical_patient_id = reconciled_event.canonical_patient_id
        logger.info("handle_timeline_updated: data=%s, patient=%s", reconciled_event_json, canonical_patient_id)
        
        # Fetch the patient timeline first
        patient_timeline = await self._fetch_patient_timeline_latest(canonical_patient_id)
        # Generate an agentic prompt for downstream agent (LLM + RAG)
        patient_overview_info = patient_timeline.to_agent_prompt()
        logger.info("agent_request: data=%s", patient_overview_info)
        result = await self.agentic_handler.send_message(
            f"Recommended next steps for patient: {patient_overview_info}"
        )
        logger.info("agent_response: data=%s", result)

        # Try to parse as JSON; if it fails, use the result as-is as the summary
        try:
            result_json = json.loads(result)
            summary = result_json.get("recommend", result)
            risk_tier = result_json.get("risk", "medium")
        except (json.JSONDecodeError, ValueError):
            # LLM returned plain text, not JSON
            summary = result
            risk_tier = "medium"  # Default to medium risk

        recommendation = PatientRecommendation(
            canonical_patient_id=canonical_patient_id,
            summary=summary,
            risk_tier=risk_tier
        )

        await self.data_provider.insert_recommendation(recommendation=recommendation)
