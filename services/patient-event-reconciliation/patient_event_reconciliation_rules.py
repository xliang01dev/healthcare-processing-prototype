from typing import Optional

from pydantic import BaseModel

from patient_event_models import EventLog, ReconciledEvent
from shared.event_models import (
    MedicareEvent,
    HospitalEvent,
    LabEvent
)

class PatientEventReconciliationRules:
    """
    Reconciliation rules and priority logic for merging patient events from multiple sources.

    AUTHORITY HIERARCHY:

    Medicare (Insurance/Enrollment):
    - plan_type, primary_care_provider_npi, enrollment_date
    - Source of truth for insurance coverage

    Hospital (Encounter):
    - admission_date, discharge_date
    - primary_diagnosis_icd10, attending_physician_npi
    - Source of truth for clinical encounters

    Lab (Test Results):
    - Accumulates all test results (test_ordered, test_date, result_value, result_unit, reference_range)
    - Appended to lab_results array

    Normalization (all sources):
    - Hospital names (UPPERCASE) → mixed-case (normalize to Medicare/Lab format)
    - Hospital gender ("Male"/"Female") → M/F (normalize to Medicare/Lab format)
    - Different field names (Lab's patient_first_name vs Medicare/Hospital first_name) → unified first_name

    Demographics in ReconciledEvent:
    - first_name, last_name, gender are normalized and can be used to update golden_record
    - Authority: Medicare > Hospital > Lab (first non-null wins)
    """

    async def reconcile_events(self, canonical_patient_id: str, event_logs: list[EventLog]) -> ReconciledEvent:
        """Reconcile a list of events for a patient into a single ReconciledEvent snapshot."""
        if not event_logs:
            return None

        event_models = [self._convert_event_log_to_model(event_log) for event_log in event_logs]
        return self._apply_reconciliation_logic(canonical_patient_id, event_models)

    def _convert_event_log_to_model(self, event_log: EventLog) -> BaseModel:
        """Convert raw event_logs payload into typed source system model."""
        if event_log.source_system_id == "Medicare":
            return MedicareEvent.model_validate(event_log.payload)
        elif event_log.source_system_id == "Hospital":
            return HospitalEvent.model_validate(event_log.payload)
        elif event_log.source_system_id == "Labs":
            return LabEvent.model_validate(event_log.payload)
        else:
            raise ValueError(f"Unknown source_system_id: {event_log.source_system_id}")

    def _apply_reconciliation_logic(
            self,
            canonical_patient_id: str,
            events: list[BaseModel]
    ) -> ReconciledEvent:
        """
        Apply reconciliation rules to produce a single ReconciledEvent.

        Rules:
        1. Medicare: plan_type, primary_care_provider_npi are authoritative
        2. Hospital: admission_date, discharge_date, primary_diagnosis_icd10, attending_physician_npi are authoritative
        3. Lab: test results are accumulated (never overwritten)
        4. Normalization: Hospital names (UPPERCASE) and gender ("Male"/"Female") normalized
        5. Names: Use first non-null value (Medicare > Hospital > Lab, after normalization)
        """
        reconciled = ReconciledEvent(canonical_patient_id=canonical_patient_id)

        # Accumulate lab results for later
        lab_results_list = []

        for event in events:
            if isinstance(event, MedicareEvent):
                # Medicare: demographics (authoritative source)
                if not reconciled.first_name and event.first_name:
                    reconciled.first_name = self._normalize_name(event.first_name)
                if not reconciled.last_name and event.last_name:
                    reconciled.last_name = self._normalize_name(event.last_name)
                if not reconciled.gender and event.gender:
                    reconciled.gender = self._normalize_gender(event.gender)

                # Medicare: insurance and enrollment
                reconciled.primary_plan = event.plan_type or reconciled.primary_plan
                reconciled.member_id = event.source_patient_id or reconciled.member_id  # medicare_id IS the identifier

                # Medicare provider NPI
                if event.primary_care_provider_npi:
                    reconciled.care_team.append(f"PCP (Medicare): {event.primary_care_provider_npi}")

            elif isinstance(event, HospitalEvent):
                # Hospital: demographics (fallback if Medicare missing)
                if not reconciled.first_name and event.first_name:
                    reconciled.first_name = self._normalize_name(event.first_name)
                if not reconciled.last_name and event.last_name:
                    reconciled.last_name = self._normalize_name(event.last_name)
                if not reconciled.gender and event.gender:
                    reconciled.gender = self._normalize_gender(event.gender)

                # Hospital: encounter dates and diagnosis
                if event.admission_date:
                    reconciled.admission_date = event.admission_date

                if event.discharge_date:
                    reconciled.discharge_date = event.discharge_date

                # Primary diagnosis from Hospital
                if event.primary_diagnosis_icd10:
                    reconciled.active_diagnoses.append(event.primary_diagnosis_icd10)

                # Attending physician from Hospital
                if event.attending_physician_npi:
                    reconciled.attending_physician = event.attending_physician_npi
                    reconciled.care_team.append(f"Attending: {event.attending_physician_npi}")

                # Gender normalization: Hospital "Male"/"Female" → "M"/"F"
                normalized_gender = self._normalize_gender(event.gender)
                # (Don't store gender on ReconciledEvent as it's not a field, but could validate)

            elif isinstance(event, LabEvent):
                # Lab: demographics (fallback if Medicare/Hospital missing)
                if not reconciled.first_name and event.patient_first_name:
                    reconciled.first_name = self._normalize_name(event.patient_first_name)
                if not reconciled.last_name and event.patient_last_name:
                    reconciled.last_name = self._normalize_name(event.patient_last_name)
                if not reconciled.gender and event.gender:
                    reconciled.gender = self._normalize_gender(event.gender)

                # Lab: accumulate all test results
                lab_result_str = f"{event.test_ordered} ({event.test_date}): {event.result_value} {event.result_unit}"
                if event.reference_range:
                    lab_result_str += f" (ref: {event.reference_range})"
                lab_results_list.append(lab_result_str)

        # Populate lab results
        reconciled.lab_results = list(dict.fromkeys(lab_results_list))  # Remove duplicates

        # Remove duplicate care_team members
        reconciled.care_team = list(dict.fromkeys(reconciled.care_team))

        return reconciled

    def _normalize_name(self, name: Optional[str]) -> Optional[str]:
        """Convert Hospital UPPERCASE names to mixed-case."""
        if not name:
            return None
        # Simple conversion: capitalize first letter, lowercase rest
        return name.capitalize()

    def _normalize_gender(self, gender: Optional[str]) -> Optional[str]:
        """Convert Hospital gender encoding ('Male'/'Female') to M/F."""
        if not gender:
            return None
        if gender in ("Male", "M"):
            return "M"
        elif gender in ("Female", "F"):
            return "F"
        return gender