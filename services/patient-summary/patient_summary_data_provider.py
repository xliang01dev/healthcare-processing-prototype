from shared.data_provider import DataProvider


class PatientSummaryDataProvider(DataProvider):
    """
    Postgres access for the Patient Summary service.
    Schema: patient_summary (recommendations)
    """

    async def fetch_latest_recommendation(self, canonical_patient_id: str) -> dict | None:
        # TODO: SELECT * FROM patient_summary.recommendations
        #   WHERE canonical_patient_id = $1
        #   ORDER BY generated_at DESC LIMIT 1;
        return None

    async def fetch_recommendations(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> list:
        # TODO: SELECT * FROM patient_summary.recommendations
        #   WHERE canonical_patient_id = $1
        #   ORDER BY generated_at DESC
        #   LIMIT $2 OFFSET $3;
        return []

    async def insert_recommendation(self, recommendation: dict) -> None:
        # TODO: INSERT INTO patient_summary.recommendations
        #   (canonical_patient_id, summary, risk_tier, generated_at, content_hash)
        #   VALUES ($1, $2, $3, NOW(), $4);
        #   Deduplication: hash check → structural diff → cosine similarity tiebreaker.
        pass
