"""
Patient pool and random event builders.

Six synthetic patients appear across all three sources with intentional field
discrepancies that exercise the reconciliation normalisation logic:

  - first_name / last_name: mixed-case in A and C; UPPERCASE in B (hospital convention)
  - gender: "M"/"F" in A and C; "Male"/"Female" in B
  - source_patient_id: different per source (MRN for B, lab ID for C, medicare_id for A)
  - medicare_id: shared anchor present in all three sources
"""

import random
from datetime import date, timedelta

from models import (
    HydrateEvent,
    HospitalEvent,
    LabEvent,
    MedicareEvent,
    make_message_id,
)

# ---------------------------------------------------------------------------
# Patient pool
# ---------------------------------------------------------------------------

PATIENTS: list[dict] = [
    {
        "medicare_id": "1EG4TE5MK72",
        "mrn": "MRN-00421",
        "lab_id": "LAB-09921",
        "first_name": "John",
        "last_name": "Smith",
        "dob": date(1945, 3, 14),
        "gender": "M",
        "gender_hospital": "Male",
        "ssn_last4": "4821",
        "state": "MA",
        "zip_code": "02101",
        "plan_type": "Medicare Advantage (Part C)",
        "pcp_npi": "1234567890",
    },
    {
        "medicare_id": "2WN5TR8PX91",
        "mrn": "MRN-00833",
        "lab_id": "LAB-03310",
        "first_name": "Mary",
        "last_name": "Johnson",
        "dob": date(1952, 7, 22),
        "gender": "F",
        "gender_hospital": "Female",
        "ssn_last4": "7392",
        "state": "FL",
        "zip_code": "33101",
        "plan_type": "Original Medicare (Part A & B)",
        "pcp_npi": "2345678901",
    },
    {
        "medicare_id": "3KP9LF2QR45",
        "mrn": "MRN-01147",
        "lab_id": "LAB-07734",
        "first_name": "Robert",
        "last_name": "Williams",
        "dob": date(1939, 11, 5),
        "gender": "M",
        "gender_hospital": "Male",
        "ssn_last4": "2190",
        "state": "TX",
        "zip_code": "75201",
        "plan_type": "Medicare Supplement (Medigap)",
        "pcp_npi": "3456789012",
    },
    {
        "medicare_id": "4RT7GH3NJ18",
        "mrn": "MRN-02291",
        "lab_id": "LAB-01854",
        "first_name": "Patricia",
        "last_name": "Brown",
        "dob": date(1960, 5, 19),
        "gender": "F",
        "gender_hospital": "Female",
        "ssn_last4": "6614",
        "state": "CA",
        "zip_code": "90001",
        "plan_type": "Medicare Advantage (Part C)",
        "pcp_npi": "4567890123",
    },
    {
        "medicare_id": "5MX2YC6VB83",
        "mrn": "MRN-03885",
        "lab_id": "LAB-05527",
        "first_name": "James",
        "last_name": "Davis",
        "dob": date(1948, 9, 30),
        "gender": "M",
        "gender_hospital": "Male",
        "ssn_last4": "9037",
        "state": "NY",
        "zip_code": "10001",
        "plan_type": "Original Medicare (Part A & B)",
        "pcp_npi": "5678901234",
    },
    {
        "medicare_id": "6SZ4DQ9WA56",
        "mrn": "MRN-04419",
        "lab_id": "LAB-08863",
        "first_name": "Linda",
        "last_name": "Miller",
        "dob": date(1955, 1, 8),
        "gender": "F",
        "gender_hospital": "Female",
        "ssn_last4": "3758",
        "state": "OH",
        "zip_code": "43001",
        "plan_type": "Medicare Part D",
        "pcp_npi": "6789012345",
    },
]

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

_MEDICARE_EVENT_TYPES = [
    "medicare_enrollment",
    "medicare_claims",
    "hcc_risk_score_update",
]

_HOSPITAL_EVENT_TYPES = [
    "hospital_encounter",
    "emergency_visit",
    "outpatient_procedure",
]

# (icd10_code, description) — used to populate primary_diagnosis_icd10
_ICD10_CODES: list[tuple[str, str]] = [
    ("E11.9",  "Type 2 diabetes mellitus without complications"),
    ("I10",    "Essential hypertension"),
    ("I25.10", "Atherosclerotic heart disease, native coronary artery"),
    ("J18.9",  "Pneumonia, unspecified organism"),
    ("N18.3",  "Chronic kidney disease, stage 3"),
    ("M54.5",  "Low back pain"),
    ("K21.0",  "Gastroesophageal reflux disease with esophagitis"),
    ("J44.1",  "COPD with acute exacerbation"),
    ("F32.1",  "Major depressive episode, moderate"),
    ("Z51.11", "Encounter for antineoplastic chemotherapy"),
]

# (test_ordered, result_value, result_unit, reference_range)
_LAB_TESTS: list[tuple[str, str, str, str]] = [
    ("HbA1c",            "6.5",  "%",               "4.0-5.6"),
    ("LDL Cholesterol",  "142",  "mg/dL",           "<100"),
    ("eGFR",             "58",   "mL/min/1.73m²",   ">60"),
    ("TSH",              "3.2",  "mIU/L",           "0.4-4.0"),
    ("WBC",              "7.8",  "x10³/µL",         "4.5-11.0"),
    ("Hemoglobin",       "12.1", "g/dL",            "12.0-17.5"),
    ("Creatinine",       "1.4",  "mg/dL",           "0.7-1.3"),
    ("Glucose (Fasting)","118",  "mg/dL",           "70-100"),
    ("INR",              "2.4",  "ratio",           "0.8-1.2"),
    ("PSA",              "4.8",  "ng/mL",           "<4.0"),
]

_PHYSICIAN_NPIS = [
    "7890123456",
    "8901234567",
    "9012345678",
    "0123456789",
    "1122334455",
]

# ---------------------------------------------------------------------------
# Builders — return (nats_subject, event_model)
# ---------------------------------------------------------------------------

def _days_ago(n: int) -> date:
    return date.today() - timedelta(days=n)


def build_hydrate(patient: dict) -> tuple[str, HydrateEvent]:
    return "patient.hydrate", HydrateEvent(
        operation="add",
        medicare_id=patient["medicare_id"],
        first_name=patient["first_name"],
        last_name=patient["last_name"],
        date_of_birth=patient["dob"],
        gender=patient["gender"],
    )


def build_medicare(patient: dict) -> tuple[str, MedicareEvent]:
    return "raw.source-a", MedicareEvent(
        message_id=make_message_id(patient["medicare_id"], "source-a"),
        source_patient_id=patient["medicare_id"],
        event_type=random.choice(_MEDICARE_EVENT_TYPES),
        medicare_id=patient["medicare_id"],
        first_name=patient["first_name"],
        last_name=patient["last_name"],
        date_of_birth=patient["dob"],
        gender=patient["gender"],
        enrollment_date=_days_ago(random.randint(365, 3650)),
        plan_type=patient["plan_type"],
        primary_care_provider_npi=patient["pcp_npi"],
        state=patient["state"],
        zip_code=patient["zip_code"],
    )


def build_hospital(patient: dict) -> tuple[str, HospitalEvent]:
    icd_code, _ = random.choice(_ICD10_CODES)
    admission = _days_ago(random.randint(7, 180))
    discharge = admission + timedelta(days=random.randint(1, 7))
    return "raw.source-b", HospitalEvent(
        message_id=make_message_id(patient["mrn"], "source-b"),
        source_patient_id=patient["mrn"],
        event_type=random.choice(_HOSPITAL_EVENT_TYPES),
        medicare_id=patient["medicare_id"],
        ssn_last4=patient["ssn_last4"],
        first_name=patient["first_name"].upper(),   # hospital EHR returns UPPERCASE
        last_name=patient["last_name"].upper(),
        date_of_birth=patient["dob"],
        gender=patient["gender_hospital"],           # "Male" / "Female" encoding
        admission_date=admission,
        discharge_date=discharge,
        primary_diagnosis_icd10=icd_code,
        attending_physician_npi=random.choice(_PHYSICIAN_NPIS),
    )


def build_lab(patient: dict) -> tuple[str, LabEvent]:
    test, value, unit, ref_range = random.choice(_LAB_TESTS)
    return "raw.source-c", LabEvent(
        message_id=make_message_id(patient["lab_id"], "source-c"),
        source_patient_id=patient["lab_id"],
        medicare_id=patient["medicare_id"],
        patient_first_name=patient["first_name"],   # different field name from A/B
        patient_last_name=patient["last_name"],
        date_of_birth=patient["dob"],
        gender=patient["gender"],                    # "M"/"F" — agrees with A, conflicts with B
        test_ordered=test,
        test_date=_days_ago(random.randint(1, 30)),
        result_value=value,
        result_unit=unit,
        reference_range=ref_range,
    )


_BUILDERS = {
    "i": build_hydrate,
    "a": build_medicare,
    "b": build_hospital,
    "c": build_lab,
}


def build(source: str, patient: dict) -> tuple[str, object]:
    """Build an event for the given source key ('i', 'a', 'b', 'c')."""
    return _BUILDERS[source](patient)


def build_random(patient: dict) -> tuple[str, object]:
    """Pick a random source and build its event for the given patient."""
    return build(random.choice(list(_BUILDERS)), patient)
