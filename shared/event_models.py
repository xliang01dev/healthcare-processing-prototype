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

    # 10 clinical fields
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

    # 10 clinical fields
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

