"""
Pydantic event models for each inbound source.

Envelope fields (all events):
  message_id        — sha256(source_patient_id + version + source_system)
  source_system     — "source-a" | "source-b" | "source-c"
  source_patient_id — the source's own ID for this patient
  event_type        — what happened; used by reconciliation to determine priority

Clinical fields are the 10 business fields per source. Intentional format conflicts
across sources exercise the reconciliation normalisation logic:

  first_name / last_name  — Source B returns UPPERCASE (hospital EHR convention)
  gender                  — Source A and C use "M"/"F"; Source B uses "Male"/"Female"
  patient_first_name      — Source C uses a different field name for the same concept
"""

import hashlib
from datetime import date

from pydantic import BaseModel


def make_message_id(source_patient_id: str, source_system: str, version: int = 1) -> str:
    """Deterministic message ID — sha256(source_patient_id + version + source_system)."""
    raw = f"{source_patient_id}{version}{source_system}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# patient.hydrate
# ---------------------------------------------------------------------------

class HydrateEvent(BaseModel):
    """
    Seeds patient_data.patients with a canonical identity record.

    Published to: patient.hydrate
    Consumed by:  Patient Data Service → upsert_patient(), upsert_golden_record()

    operation:
      "add"    — create new canonical patient (first hydration)
      "update" — refresh demographic fields on existing record
      "remove" — tombstone; does not hard-delete canonical records
    """
    operation: str          # "add" | "update" | "remove"
    medicare_id: str        # shared_identifier — cross-source anchor (MBI equivalent)
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str             # "M" | "F"


# ---------------------------------------------------------------------------
# raw.source-a  (Medicare)
# ---------------------------------------------------------------------------

class MedicareEvent(BaseModel):
    """
    Medicare enrollment and claims data.

    Published to: raw.source-a
    Consumed by:  Patient Data Service → identity resolution → reconcile.{canonical_id}

    Reconciliation notes:
      - source_patient_id == medicare_id (Medicare IS the identity authority)
      - gender "M"/"F" is the canonical encoding; Source B conflicts with "Male"/"Female"
      - first_name / last_name are mixed-case; Source B returns UPPERCASE
    """
    # Envelope
    message_id: str
    source_system: str = "source-medicare"
    source_patient_id: str      # medicare_id — source's own patient identifier
    event_type: str             # "medicare_enrollment" | "medicare_claims" | "hcc_risk_score_update"

    # 10 clinical fields
    medicare_id: str            # shared anchor — same value used by Source B and C
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
# raw.source-b  (Hospital EHR)
# ---------------------------------------------------------------------------

class HospitalEvent(BaseModel):
    """
    Hospital EHR encounter data.

    Published to: raw.source-b
    Consumed by:  Patient Data Service → identity resolution → reconcile.{canonical_id}

    Reconciliation conflicts (intentional):
      - first_name / last_name: UPPERCASE — normalise to mixed-case when reconciling
      - gender: "Male" / "Female" — normalise to "M" / "F" to match Source A and C
      - medicare_id: present as a cross-reference field; Source B's own patient ID is the MRN
    """
    # Envelope
    message_id: str
    source_system: str = "source-hospital"
    source_patient_id: str      # hospital MRN — Source B's own patient identifier
    event_type: str             # "hospital_encounter" | "emergency_visit" | "outpatient_procedure"

    # 10 clinical fields
    medicare_id: str            # shared anchor — overlaps with Source A and C
    ssn_last4: str
    first_name: str             # UPPERCASE — hospital EHR convention; conflicts with Source A/C
    last_name: str              # UPPERCASE
    date_of_birth: date         # overlaps with A and C — mismatch triggers conflict flag
    gender: str                 # "Male" | "Female" — encoding conflict with A ("M"/"F") and C ("M"/"F")
    admission_date: date
    discharge_date: date
    primary_diagnosis_icd10: str
    attending_physician_npi: str


# ---------------------------------------------------------------------------
# raw.source-c  (Labs)
# ---------------------------------------------------------------------------

class LabEvent(BaseModel):
    """
    Lab result data.

    Published to: raw.source-c
    Consumed by:  Patient Data Service → identity resolution → reconcile.{canonical_id}

    Reconciliation notes:
      - patient_first_name / patient_last_name: different field names from Source A/B for the
        same demographic concept — reconciliation maps these to first_name / last_name
      - gender "M"/"F" agrees with Source A; both conflict with Source B's "Male"/"Female"
      - medicare_id present as cross-reference; Source C's own ID is the lab patient ID
    """
    # Envelope
    message_id: str
    source_system: str = "source-labs"
    source_patient_id: str      # lab patient ID — Source C's own identifier
    event_type: str = "lab_result"

    # 10 clinical fields
    medicare_id: str            # shared anchor — overlaps with A and B
    patient_first_name: str     # different field name from A's "first_name" — same concept
    patient_last_name: str      # different field name from A's "last_name"
    date_of_birth: date         # overlaps with A and B
    gender: str                 # "M" | "F" — agrees with A, conflicts with B
    test_ordered: str           # e.g. "HbA1c", "LDL Cholesterol"
    test_date: date
    result_value: str           # e.g. "6.5"
    result_unit: str            # e.g. "%", "mg/dL"
    reference_range: str        # e.g. "4.0-5.6"
