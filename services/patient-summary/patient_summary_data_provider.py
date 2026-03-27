import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "shared"))

from data_provider import DataProvider


class PatientSummaryDataProvider(DataProvider):
    """
    Postgres access for the Patient Summary (LLM) service.
    Schema: llm (llm_recommendations, llm_pending_assessments)
    """

    async def fetch_latest_recommendation(self, canonical_patient_id: str) -> dict | None:
        # TODO: SELECT * FROM llm.llm_recommendations
        #   WHERE canonical_patient_id = $1
        #   ORDER BY generated_at DESC LIMIT 1;
        return None

    async def fetch_recommendations(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> list:
        # TODO: SELECT * FROM llm.llm_recommendations
        #   WHERE canonical_patient_id = $1
        #   ORDER BY generated_at DESC
        #   LIMIT $2 OFFSET $3;
        return []

    async def insert_recommendation(self, recommendation: dict) -> None:
        # TODO: INSERT INTO llm.llm_recommendations
        #   (canonical_patient_id, summary, risk_tier, generated_at, content_hash)
        #   VALUES ($1, $2, $3, NOW(), $4);
        #   Deduplication: hash check → structural diff → cosine similarity tiebreaker.
        pass

    async def fetch_pending_assessments(self) -> list:
        # TODO: SELECT * FROM llm.llm_pending_assessments
        #   WHERE scheduled_after < NOW() AND status = 'pending';
        return []

    async def update_assessment_status(
        self, canonical_patient_id: str, status: str
    ) -> None:
        # TODO: UPDATE llm.llm_pending_assessments SET status = $2
        #   WHERE canonical_patient_id = $1;
        #   status values: 'pending' | 'processing' | 'done' | 'failed'
        pass
