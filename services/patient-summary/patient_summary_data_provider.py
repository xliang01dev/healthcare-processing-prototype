import hashlib
import logging

from shared.data_provider import DataProvider
from patient_summary_models import PatientRecommendation

logger = logging.getLogger(__name__)


class PatientSummaryDataProvider(DataProvider):
    """
    Postgres access for the Patient Summary service.
    Schema: patient_summary (recommendations) + patient_timeline (materialized view)
    """

    # async def fetch_patient_timeline_latest(self, canonical_patient_id: str) -> PatientTimeline | None:
    #     """Fetch latest timeline event from materialized view (for fast lookups)."""
    #     logger.info("fetch_patient_timeline_latest: canonical_patient_id=%s", canonical_patient_id)
    #     assert self._reader is not None
    #     async with self._reader.acquire() as conn:
    #         row = await conn.fetchrow(
    #             """
    #             SELECT * FROM patient_timeline.patient_timeline
    #             WHERE canonical_patient_id = $1
    #             """,
    #             canonical_patient_id,
    #         )
    #         if row:
    #             return PatientTimeline.model_validate(dict(row))
    #         return None

    async def fetch_latest_recommendation(self, canonical_patient_id: str) -> PatientRecommendation | None:
        """Fetch the most recent recommendation for a patient."""
        logger.info("fetch_latest_recommendation: canonical_patient_id=%s", canonical_patient_id)

        sql = """
        SELECT id, canonical_patient_id, summary, risk_tier, content_hash, generated_at
        FROM patient_summary.recommendations
        WHERE canonical_patient_id = $1
        ORDER BY generated_at DESC
        LIMIT 1
        """

        row = await self.fetch_row(sql, canonical_patient_id)
        return PatientRecommendation.model_validate(dict(row)) if row else None

    async def fetch_recommendations(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> list[PatientRecommendation]:
        """Fetch recommendations for a patient with pagination."""
        logger.info("fetch_recommendations: canonical_patient_id=%s page=%s page_size=%s", canonical_patient_id, page, page_size)

        sql = """
        SELECT id, canonical_patient_id, summary, risk_tier, content_hash, generated_at
        FROM patient_summary.recommendations
        WHERE canonical_patient_id = $1
        ORDER BY generated_at DESC
        LIMIT $2 OFFSET $3
        """

        offset = (page - 1) * page_size
        rows = await self.fetch_rows(sql, canonical_patient_id, page_size, offset)
        return [PatientRecommendation.model_validate(dict(row)) for row in rows]

    async def insert_recommendation(self, recommendation: PatientRecommendation) -> int:
        """
        Insert a recommendation for a patient.

        Args:
            recommendation: PatientRecommendation model with:
                - canonical_patient_id: Patient UUID
                - summary: Short summary of recommendation
                - risk_tier: Risk level (e.g., "high", "medium", "low")

        Returns:
            int: ID of the inserted recommendation

        Note:
            Content hash is computed from the summary. Exact duplicate detection
            should be handled at the service level via content_hash lookup.
        """
        canonical_patient_id = recommendation.canonical_patient_id
        summary = recommendation.summary
        risk_tier = recommendation.risk_tier

        # Compute content hash from summary for deduplication
        content_hash = hashlib.sha256(summary.encode()).hexdigest()

        logger.info(
            "insert_recommendation: canonical_patient_id=%s risk_tier=%s hash=%s",
            canonical_patient_id,
            risk_tier,
            content_hash[:8],
        )

        sql = """
        INSERT INTO patient_summary.recommendations (
            canonical_patient_id,
            summary,
            risk_tier,
            content_hash,
            generated_at
        ) VALUES ($1, $2, $3, $4, NOW())
        RETURNING id
        """

        result = await self.execute_returning(
            sql,
            canonical_patient_id,
            summary,
            risk_tier,
            content_hash,
        )

        if result is None:
            raise ValueError(f"Failed to insert recommendation for patient {canonical_patient_id}")

        return result["id"]
