from models import (
    ConflictsResponse,
    PatientInfoResponse,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationsResponse,
    TimelineResponse,
)


class PatientService:
    async def get_patient_info(self, canonical_patient_id: str) -> PatientInfoResponse:
        # TODO: Call MPI service → mpi.mpi_patients + mpi.mpi_source_identities.
        return PatientInfoResponse()

    async def get_patient_timelines(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> TimelineResponse:
        # TODO: Call Timeline service → timeline.patient_timeline (materialized view).
        return TimelineResponse()

    async def get_patient_recommendation(
        self, canonical_patient_id: str
    ) -> RecommendationResponse:
        # TODO: Call LLM Summary service → CacheService first,
        #   fallback to patient_summary.recommendations ORDER BY generated_at DESC LIMIT 1.
        return RecommendationResponse()

    async def get_patient_recommendations(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> RecommendationsResponse:
        # TODO: Call LLM Summary service → patient_summary.recommendations ORDER BY generated_at DESC.
        return RecommendationsResponse()

    async def get_patient_conflicts(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> ConflictsResponse:
        # TODO: Call Reconciliation service → reconciliation.reconciliation_conflicts ORDER BY created_at DESC.
        return ConflictsResponse()

    async def refresh_recommendation(self, body: RecommendationRequest) -> dict:
        # TODO: Call LLM Summary service to trigger agent session inference (mode='agent').
        #   Only HTTP-triggered write path into patient_summary.recommendations.
        return {"stub": True}
