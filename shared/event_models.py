"""
Pydantic event models for each inbound source system.

Envelope fields (all events):
  message_id        — sha256(source_patient_id + version + source_system)
  source_system     — "Medicare" | "Hospital" | "Labs"
  source_patient_id — the source's own ID for this patient
  event_type        — what happened; used by reconciliation to determine priority

Clinical fields are the 10 business fields per source. Intentional format conflicts
across sources exercise the reconciliation normalisation logic:

  first_name / last_name  — Hospital returns UPPERCASE (hospital EHR convention)
  gender                  — Medicare and Labs use "M"/"F"; Hospital uses "Male"/"Female"
  patient_first_name      — Labs uses a different field name for the same concept
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# raw.source-medicare  (Medicare)
# ---------------------------------------------------------------------------

class MedicareEvent(BaseModel):
    """
    Medicare enrollment and claims data.

    Published to: raw.source-medicare
    Consumed by:  Patient Data Service → identity resolution → reconcile.{canonical_id}

    Reconciliation notes:
      - source_patient_id == medicare_id (Medicare IS the identity authority)
      - gender "M"/"F" is the canonical encoding; Hospital conflicts with "Male"/"Female"
      - first_name / last_name are mixed-case; Hospital returns UPPERCASE
    """
    # Envelope
    message_id: str
    source_system: str = "Medicare"
    source_patient_id: str           # medicare_id — source's own patient identifier
    event_type: str                  # "medicare_enrollment" | "medicare_claims" | "hcc_risk_score_update"
    occurred_at: datetime            # when event occurred in Medicare system

    # 10 clinical fields (required)
    medicare_id: str            # shared anchor — same value used by Hospital and Labs
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str                 # "M" | "F"
    enrollment_date: date
    plan_type: str              # "Medicare Advantage (Part C)" | "Original Medicare (Part A & B)" | ...
    primary_care_provider_npi: str
    state: str
    zip_code: str

    # Optional additional coverage fields for comprehensive timeline
    member_id: Optional[str] = None
    eligibility_status: Optional[str] = None    # "active", "terminated", "suspended"
    network_status: Optional[str] = None        # "in-network", "out-of-network"
    authorization_required: Optional[bool] = None
    authorization_status: Optional[str] = None  # authorization approval status


# ---------------------------------------------------------------------------
# raw.source-hospital  (Hospital EHR)
# ---------------------------------------------------------------------------

class HospitalEvent(BaseModel):
    """
    Hospital EHR encounter data.

    Published to: raw.source-hospital
    Consumed by:  Patient Data Service → identity resolution → reconcile.{canonical_id}

    Reconciliation conflicts (intentional):
      - first_name / last_name: UPPERCASE — normalise to mixed-case when reconciling
      - gender: "Male" / "Female" — normalise to "M" / "F" to match Medicare and Labs
      - medicare_id: present as a cross-reference field; Hospital's own patient ID is the MRN
    """
    # Envelope
    message_id: str
    source_system: str = "Hospital"
    source_patient_id: str              # hospital MRN — Hospital's own patient identifier
    event_type: str                     # "hospital_encounter" | "emergency_visit" | "outpatient_procedure"
    occurred_at: datetime               # when event occurred in Hospital system

    # 10 clinical fields (required)
    medicare_id: str            # shared anchor — overlaps with Medicare and Labs
    ssn_last4: str
    first_name: str             # UPPERCASE — hospital EHR convention; conflicts with Medicare/Labs
    last_name: str              # UPPERCASE
    date_of_birth: date         # overlaps with Medicare and Labs — mismatch triggers conflict flag
    gender: str                 # "Male" | "Female" — encoding conflict with Medicare ("M"/"F") and Labs ("M"/"F")
    admission_date: date
    discharge_date: date
    primary_diagnosis_icd10: str
    attending_physician_npi: str

    # Optional additional clinical fields for comprehensive timeline
    facility_name: Optional[str] = None
    encounter_status: Optional[str] = None      # "active", "discharged", "pending"
    procedures: Optional[list[str]] = None      # CPT codes and descriptions
    medications: Optional[list[str]] = None     # Current medications
    allergies: Optional[list[str]] = None       # Drug/food allergies
    clinical_notes: Optional[str] = None        # Provider narrative


# ---------------------------------------------------------------------------
# raw.source-labs  (Labs)
# ---------------------------------------------------------------------------

class LabEvent(BaseModel):
    """
    Lab result data.

    Published to: raw.source-labs
    Consumed by:  Patient Data Service → identity resolution → reconcile.{canonical_id}

    Reconciliation notes:
      - patient_first_name / patient_last_name: different field names from Medicare/Hospital for the
        same demographic concept — reconciliation maps these to first_name / last_name
      - gender "M"/"F" agrees with Medicare; both conflict with Hospital's "Male"/"Female"
      - medicare_id present as cross-reference; Labs's own ID is the lab patient ID
    """
    # Envelope
    message_id: str
    source_system: str = "Labs"
    source_patient_id: str              # lab patient ID — Labs's own identifier
    event_type: str = "lab_result"
    occurred_at: datetime               # when event occurred in Labs system

    # 10 clinical fields
    medicare_id: str            # shared anchor — overlaps with Medicare and Hospital
    patient_first_name: str     # different field name from Medicare's "first_name" — same concept
    patient_last_name: str      # different field name from Medicare's "last_name"
    date_of_birth: date         # overlaps with Medicare and Hospital
    gender: str                 # "M" | "F" — agrees with Medicare, conflicts with Hospital
    test_ordered: str           # e.g. "HbA1c", "LDL Cholesterol"
    test_date: date
    result_value: str           # e.g. "6.5"
    result_unit: str            # e.g. "%", "mg/dL"
    reference_range: str        # e.g. "4.0-5.6"


# ---------------------------------------------------------------------------
# Reconciled Event
# ---------------------------------------------------------------------------


class ReconciledEvent(BaseModel):
    """
    Denormalized snapshot of patient's current clinical and insurance state after reconciliation.

    Each resolved_event row captures the complete state of a patient at a point in time
    across Medicare, Hospital, and Lab systems. Forms a timeline of how patient state evolved.
    """
    id: int = Field(description="Primary key")
    canonical_patient_id: UUID = Field(description="Patient UUID")
    event_log_ids: list[int] = Field(description="IDs of all event_logs reconciled in this window")
    event_processing_start: datetime = Field(description="When debounce window opened")
    event_processing_end: datetime = Field(description="When reconciliation was triggered/completed")
    created_at: Optional[datetime] = Field(None, description="When this reconciliation was created")

    # Demographics (normalized, can override golden_record)
    first_name: Optional[str] = Field(None, description="Patient first name (normalized to mixed-case)")
    last_name: Optional[str] = Field(None, description="Patient last name (normalized to mixed-case)")
    gender: Optional[str] = Field(None, description="Patient gender (M or F, normalized)")

    # Insurance & Coverage
    primary_plan: Optional[str] = Field(None, description="Primary insurance plan name")
    member_id: Optional[str] = Field(None, description="Insurance member ID")
    eligibility_status: Optional[str] = Field(None, description="active, terminated, suspended")
    network_status: Optional[str] = Field(None, description="in-network, out-of-network")
    authorization_required: Optional[bool] = Field(None, description="Whether prior auth is required")
    authorization_status: Optional[str] = Field(None, description="Authorization approval status")

    # Current Encounter
    admission_date: Optional[datetime] = Field(None, description="Hospital admission date")
    discharge_date: Optional[datetime] = Field(None, description="Hospital discharge date")
    facility_name: Optional[str] = Field(None, description="Hospital or lab facility name")
    attending_physician: Optional[str] = Field(None, description="Responsible physician")
    encounter_status: Optional[str] = Field(None, description="active, discharged, pending")

    # Clinical - searchable text arrays
    diagnosis_codes: list[str] = Field(default_factory=list, description="ICD diagnosis codes")
    active_diagnoses: list[str] = Field(default_factory=list, description="Active diagnosis descriptions")
    procedures: list[str] = Field(default_factory=list, description="Procedure codes and descriptions")
    medications: list[str] = Field(default_factory=list, description="Current medication names")
    allergies: list[str] = Field(default_factory=list, description="Drug/food allergies")
    lab_results: list[str] = Field(default_factory=list, description="Lab test names and values")
    care_team: list[str] = Field(default_factory=list, description="Provider names on care team")
    scheduled_followups: list[str] = Field(default_factory=list, description="Scheduled appointments and referrals")
    quality_flags: list[str] = Field(default_factory=list, description="Risk flags, complications, adverse events")

    # Unstructured
    clinical_notes: Optional[str] = Field(None, description="Provider narrative notes")
    resolution_log: Optional[str] = Field(None, description="How conflicts were resolved during reconciliation")
    created_at: datetime = Field(description="When this reconciliation was created")


# ---------------------------------------------------------------------------
# Patient Timeline
# ---------------------------------------------------------------------------


class PatientTimeline(BaseModel):
    """
    Latest timeline event for a patient from the materialized view.

    This is the most recent reconciled state per patient, used for fast O(1) lookups
    and as the foundation for patient summaries and dashboards.

    Queried from: patient_timeline.patient_timeline (materialized view)
    Updated by:   Patient Timeline Service (via REFRESH MATERIALIZED VIEW CONCURRENTLY)
    """
    id: int = Field(description="Primary key from timeline_events")
    canonical_patient_id: UUID = Field(description="Patient UUID")
    event_log_ids: list[int] = Field(description="IDs of all event_logs reconciled in this window")
    event_processing_start: datetime = Field(description="When debounce window opened")
    event_processing_end: datetime = Field(description="When reconciliation was triggered/completed")
    created_at: datetime = Field(description="When this timeline event was created")

    # Demographics (normalized)
    first_name: Optional[str] = Field(None, description="Patient first name (normalized to mixed-case)")
    last_name: Optional[str] = Field(None, description="Patient last name (normalized to mixed-case)")
    gender: Optional[str] = Field(None, description="Patient gender (M or F, normalized)")

    # Insurance & Coverage
    primary_plan: Optional[str] = Field(None, description="Primary insurance plan name")
    member_id: Optional[str] = Field(None, description="Insurance member ID")
    eligibility_status: Optional[str] = Field(None, description="active, terminated, suspended")
    network_status: Optional[str] = Field(None, description="in-network, out-of-network")
    authorization_required: Optional[bool] = Field(None, description="Whether prior auth is required")
    authorization_status: Optional[str] = Field(None, description="Authorization approval status")

    # Current Encounter
    admission_date: Optional[datetime] = Field(None, description="Hospital admission date")
    discharge_date: Optional[datetime] = Field(None, description="Hospital discharge date")
    facility_name: Optional[str] = Field(None, description="Hospital or lab facility name")
    attending_physician: Optional[str] = Field(None, description="Responsible physician")
    encounter_status: Optional[str] = Field(None, description="active, discharged, pending")

    # Clinical - searchable text arrays
    diagnosis_codes: list[str] = Field(default_factory=list, description="ICD diagnosis codes")
    active_diagnoses: list[str] = Field(default_factory=list, description="Active diagnosis descriptions")
    procedures: list[str] = Field(default_factory=list, description="Procedure codes and descriptions")
    medications: list[str] = Field(default_factory=list, description="Current medication names")
    allergies: list[str] = Field(default_factory=list, description="Drug/food allergies")
    lab_results: list[str] = Field(default_factory=list, description="Lab test names and values")
    care_team: list[str] = Field(default_factory=list, description="Provider names on care team")
    scheduled_followups: list[str] = Field(default_factory=list, description="Scheduled appointments and referrals")
    quality_flags: list[str] = Field(default_factory=list, description="Risk flags, complications, adverse events")

    # Unstructured
    clinical_notes: Optional[str] = Field(None, description="Provider narrative notes")
    resolution_log: Optional[str] = Field(None, description="How conflicts were resolved during reconciliation")

    def to_agent_prompt(self) -> str:
        """
        Format patient timeline as a natural language prompt for downstream LLM agent.

        Designed for Medicare experts to determine next steps (coverage decisions,
        authorization requirements, care coordination, etc.).

        Returns:
            str: Natural language prompt with patient demographics, coverage, encounter, and clinical data
        """
        paragraphs = []

        # Demographics paragraph
        demo = f"{self.first_name or '?'} {self.last_name or '?'}"
        if self.gender:
            demo += f" is a {self.gender.lower()}"
        demo += " patient"
        paragraphs.append(demo + ".")

        # Coverage paragraph
        coverage_parts = []
        if self.primary_plan:
            coverage_parts.append(f"enrolled in {self.primary_plan}")
        if self.member_id:
            coverage_parts.append(f"member ID {self.member_id}")
        if coverage_parts:
            coverage_text = "Patient is " + ", ".join(coverage_parts) + "."
            if self.eligibility_status:
                coverage_text += f" Eligibility status is {self.eligibility_status}."
            if self.network_status:
                coverage_text += f" {self.network_status.capitalize()} coverage."
            if self.authorization_required is not None:
                auth_req = "Required" if self.authorization_required else "Not required"
                coverage_text += f" Prior authorization is {auth_req}."
            if self.authorization_status:
                coverage_text += f" Authorization status is {self.authorization_status}."
            paragraphs.append(coverage_text)

        # Encounter paragraph
        encounter_parts = []
        if self.facility_name:
            encounter_parts.append(f"at {self.facility_name}")
        if self.admission_date:
            admitted = self.admission_date.strftime('%B %d, %Y') if hasattr(self.admission_date, 'strftime') else str(self.admission_date)
            encounter_parts.append(f"admitted {admitted}")
        if self.discharge_date:
            discharged = self.discharge_date.strftime('%B %d, %Y') if hasattr(self.discharge_date, 'strftime') else str(self.discharge_date)
            encounter_parts.append(f"discharged {discharged}")
        if self.encounter_status:
            encounter_parts.append(f"status {self.encounter_status}")
        if self.attending_physician:
            encounter_parts.append(f"under care of {self.attending_physician}")
        if encounter_parts:
            paragraphs.append("Current encounter: " + ", ".join(encounter_parts) + ".")

        # Clinical summary paragraph
        clinical_parts = []
        if self.diagnosis_codes:
            clinical_parts.append(f"Diagnoses: {', '.join(self.diagnosis_codes)}")
        if self.active_diagnoses:
            clinical_parts.append(f"Active conditions: {', '.join(self.active_diagnoses)}")
        if self.procedures:
            clinical_parts.append(f"Recent procedures: {', '.join(self.procedures)}")
        if clinical_parts:
            paragraphs.append(" ".join(clinical_parts) + ".")

        # Medications paragraph
        if self.medications:
            paragraphs.append(f"Current medications: {', '.join(self.medications)}.")

        # Allergies paragraph
        if self.allergies:
            paragraphs.append(f"Known allergies: {', '.join(self.allergies)}.")

        # Lab results paragraph
        if self.lab_results:
            paragraphs.append(f"Recent lab results: {', '.join(self.lab_results)}.")

        # Care team paragraph
        if self.care_team:
            paragraphs.append(f"Care team members: {', '.join(self.care_team)}.")

        # Risk flags paragraph
        if self.quality_flags:
            paragraphs.append(f"Risk flags and considerations: {', '.join(self.quality_flags)}.")

        # Clinical notes paragraph
        if self.clinical_notes:
            truncated = self.clinical_notes[:500] + "..." if len(self.clinical_notes) > 500 else self.clinical_notes
            paragraphs.append(f"Clinical notes: {truncated}")

        return "\n\n".join(paragraphs)


# ---------------------------------------------------------------------------
# Reconciliation Task
# ---------------------------------------------------------------------------


class ReconciliationTask(BaseModel):
    """
    Task submitted to the reconciliation worker to process a debounce window.

    Published by: Patient Event Reconciliation Service (when debounce window expires)
    Consumed by: Reconciliation Event Worker (durable queue with round-robin distribution)

    Contains the range of event_logs [start_event_log_id, end_event_log_id] to reconcile
    for a specific patient. The worker fetches these events, applies reconciliation rules,
    and publishes the result to reconciled.events.
    """
    id: str = Field(description="UUID for this task (for idempotency and tracing)")
    canonical_patient_id: str = Field(description="Patient identifier to reconcile")
    start_event_log_id: int = Field(description="First event log ID in the debounce window")
    end_event_log_id: int = Field(description="Last event log ID in the debounce window")

