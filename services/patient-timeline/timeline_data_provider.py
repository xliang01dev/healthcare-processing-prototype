import json
import logging

from shared.data_provider import DataProvider
from shared.event_models import ReconciledEvent

logger = logging.getLogger(__name__)


class TimelineDataProvider(DataProvider):
    """
    Postgres access for the Patient Timeline service.
    Schema: patient_timeline (timeline_events, patient_timeline)
    """

    async def insert_reconciled_event(self, reconciled_event: ReconciledEvent) -> None:
        """Insert a reconciled event from the reconciliation service."""
        logger.info("insert_reconciled_event: canonical_patient_id=%s", reconciled_event.canonical_patient_id)

        sql = """
        INSERT INTO patient_timeline.timeline_events (
            canonical_patient_id,
            event_log_ids,
            event_processing_start,
            event_processing_end,
            first_name,
            last_name,
            gender,
            primary_plan,
            member_id,
            eligibility_status,
            network_status,
            authorization_required,
            authorization_status,
            admission_date,
            discharge_date,
            facility_name,
            attending_physician,
            encounter_status,
            diagnosis_codes,
            active_diagnoses,
            procedures,
            medications,
            allergies,
            lab_results,
            care_team,
            scheduled_followups,
            quality_flags,
            clinical_notes,
            resolution_log
        ) VALUES (
            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20,
            $21, $22, $23, $24, $25, $26, $27, $28, $29
        )
        """

        await self.execute(
            sql,
            reconciled_event.canonical_patient_id,
            reconciled_event.event_log_ids,
            reconciled_event.event_processing_start,
            reconciled_event.event_processing_end,
            reconciled_event.first_name,
            reconciled_event.last_name,
            reconciled_event.gender,
            reconciled_event.primary_plan,
            reconciled_event.member_id,
            reconciled_event.eligibility_status,
            reconciled_event.network_status,
            reconciled_event.authorization_required,
            reconciled_event.authorization_status,
            reconciled_event.admission_date,
            reconciled_event.discharge_date,
            reconciled_event.facility_name,
            reconciled_event.attending_physician,
            reconciled_event.encounter_status,
            reconciled_event.diagnosis_codes,
            reconciled_event.active_diagnoses,
            reconciled_event.procedures,
            reconciled_event.medications,
            reconciled_event.allergies,
            reconciled_event.lab_results,
            reconciled_event.care_team,
            reconciled_event.scheduled_followups,
            reconciled_event.quality_flags,
            reconciled_event.clinical_notes,
            reconciled_event.resolution_log,
        )

    async def refresh_patient_timeline(self) -> None:
        logger.info("refresh_patient_timeline")
        await self.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY patient_timeline.patient_timeline")

    async def fetch_patient_timeline(
        self, canonical_patient_id: str, page: int, page_size: int
    ) -> list:
        logger.info("fetch_patient_timeline: canonical_patient_id=%s page=%s page_size=%s", canonical_patient_id, page, page_size)

        sql = """
        SELECT * FROM patient_timeline.patient_timeline
        WHERE canonical_patient_id = $1
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """

        return await self.fetch_rows(sql, canonical_patient_id, page_size, (page - 1) * page_size)
