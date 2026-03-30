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

from datetime import date

from pydantic import BaseModel


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
    source_patient_id: str      # medicare_id — source's own patient identifier
    event_type: str             # "medicare_enrollment" | "medicare_claims" | "hcc_risk_score_update"

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
    source_patient_id: str      # hospital MRN — Hospital's own patient identifier
    event_type: str             # "hospital_encounter" | "emergency_visit" | "outpatient_procedure"

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
    source_patient_id: str      # lab patient ID — Labs's own identifier
    event_type: str = "lab_result"

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
