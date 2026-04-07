# Reconciliation Rules (MVP)

This document describes the reconciliation logic applied by the Patient Reconciliation Worker when merging events from multiple sources (Medicare, Hospital, Labs) into a unified ReconciledEvent snapshot.

---

## Overview

The Patient Reconciliation Worker:
1. Receives a ReconciliationTask specifying a range of event_log IDs for a patient
2. Fetches those event logs from the database
3. Converts each to its typed source model (MedicareEvent, HospitalEvent, LabEvent)
4. Applies reconciliation rules to merge them
5. Publishes the result as a ReconciledEvent to `reconciled.events` topic

---

## Authority Hierarchy

Reconciliation applies a **source priority order** for conflicting fields:

### Demographics (first_name, last_name, gender)
**Priority**: Medicare > Hospital > Lab

When multiple sources provide a demographic field, the first non-null value wins (in that order). All names and gender values are normalized:
- Hospital names: UPPERCASE → mixed-case (capitalize first letter, lowercase rest)
- Hospital gender: "Male"/"Female" → "M"/"F"
- Lab field name mapping: `patient_first_name` → `first_name`, `patient_last_name` → `last_name`

### Insurance & Coverage (Medicare-Authoritative)
- `primary_plan`, `member_id`, `eligibility_status`, `network_status`, `authorization_required`, `authorization_status`

Only Medicare events populate these fields. Hospital and Lab events are ignored for insurance data.

### Encounters (Hospital-Authoritative)
- `admission_date`, `discharge_date`, `facility_name`, `encounter_status`

Only Hospital events populate encounter data. Other sources are ignored.

### Clinical Data (Cumulative/Merged)
- `diagnosis_codes`, `active_diagnoses`: Accumulated from Hospital events
- `procedures`, `medications`, `allergies`: Accumulated from Hospital events
- `lab_results`: Accumulated from Lab events (deduplicated by value)
- `clinical_notes`: Taken from Hospital events
- `care_team`: Accumulated provider NPIs from Medicare (PCP) and Hospital (Attending)

---

## Reconciliation Rules

### R1 — Use First Non-Null Value
For single-valued fields (demographics, encounter dates), use the first non-null value according to the priority hierarchy. Later events do not override earlier values once set.

### R2 — Accumulate Arrays
For multi-valued fields (medications, diagnoses, lab results, care team), accumulate all values across sources. Deduplicate exact-match values only.

### R3 — Normalize Format
Hospital data uses different encodings/conventions than Medicare/Labs:
- Names are UPPERCASE; normalize to mixed-case
- Gender uses "Male"/"Female"; normalize to "M"/"F"
- Lab uses different field names; map to canonical names

### R4 — No Conflict Resolution
The MVP does not implement conflict detection or manual review queues. When sources disagree on a field:
- Demographics: First non-null wins (priority order)
- Insurance: Medicare-only (Hospital/Lab ignored)
- Encounters: Hospital-only (Medicare/Lab ignored)
- Clinical: Accumulated (no conflict)

Conflicts are logged for future analysis but not exposed in MVP (deferred to future enhancement).

### R5 — No Versioning or Voids
The MVP writes a single ReconciledEvent snapshot per reconciliation. It does not:
- Track event versions or supersessions
- Handle corrections (events that change a prior value)
- Support void/tombstone operations
- Reprocess the timeline when events change

Each reconciliation task produces one immutable snapshot.

---

## Data Flow

```
ReconciliationTask (start_event_log_id, end_event_log_id)
    ↓
Fetch EventLogs [start...end] from event_logs table
    ↓
Convert to typed models: MedicareEvent | HospitalEvent | LabEvent
    ↓
Apply authority hierarchy and normalization
    ↓
ReconciledEvent (denormalized snapshot)
    ↓
Publish to reconciled.events
    ↓
Timeline Service inserts into timeline_events
    ↓
Refresh patient_timeline materialized view
    ↓
Publish timeline.updated event
```

---

## Source Systems

| ID | Name | Authoritative For |
|---|---|---|
| 1 | Medicare | Demographics (demographics fallback), Insurance/Coverage, Provider (PCP) |
| 2 | Hospital | Demographics (fallback), Encounters, Diagnoses, Procedures, Medications, Allergies, Clinical Notes, Provider (Attending) |
| 3 | Labs | Demographics (fallback), Lab Results |

---

## Example Reconciliation

**Events for patient canonical_id=uuid-123:**

1. **MedicareEvent**: first_name="JOHN", last_name="DOE", gender="M", plan_type="Medicare Advantage"
2. **HospitalEvent**: first_name="JOHN", last_name="DOE", gender="Male", admission_date=2026-04-01, procedures=["99213"]
3. **LabEvent**: patient_first_name="John", patient_last_name="Doe", gender="M", test_result="HbA1c: 6.5%"

**Reconciled output:**
```
canonical_patient_id: uuid-123
first_name: "John"              ← Medicare (already set)
last_name: "Doe"                ← Medicare (already set)
gender: "M"                     ← Medicare (already set)
primary_plan: "Medicare Advantage"  ← Medicare
procedures: ["99213"]           ← Hospital
lab_results: ["HbA1c: 6.5%"]   ← Lab
```

---

## Limitations & Deferred Features

### Not Implemented in MVP

- **Conflict Detection (R4)** — No logic to flag when sources disagree on facts (e.g., different dates of birth). Conflicts logged only.
- **Versioning & Corrections (R5)** — No support for event corrections that change prior values. Each snapshot is immutable.
- **Void/Tombstone Operations** — No support for events that retract prior information.
- **Late-Arrival Reprocessing** — Events arriving far after their event_date do not trigger timeline re-materialization.
- **Authority Rules by Event Type** — All fields follow the source priority order; no event-type-specific authority (e.g., "Lab results are authoritative only for test_result fields").
- **Confidence Scoring** — No numeric confidence scores for merged fields; boolean conflict flags only.

### Future Enhancements

1. **Conflict Detection** — Flag high-stakes field disagreements (DOB, gender, medication) for operator review
2. **Event Versioning** — Track corrections and voids, re-materialize timeline when events change
3. **Late-Arrival Reprocessing** — Re-materialize timeline subset when events arrive outside the normal window
4. **Per-Source Enrichment Rules** — Allow lower-authority sources to enrich fields (e.g., Lab adds medication not in Hospital record)

---

## Implementation

See `patient-reconciliation-worker/patient_event_reconciliation_rules.py`:
- `PatientEventReconciliationRules.reconcile_events()` — Main entry point
- `_convert_event_log_to_model()` — Parse event_log payload into typed model
- `_apply_reconciliation_logic()` — Apply merge rules
- `_normalize_name()`, `_normalize_gender()` — Format conversion

