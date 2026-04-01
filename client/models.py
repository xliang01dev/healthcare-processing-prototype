"""
Client-side event models and utilities for publishing events.
"""

import hashlib
from uuid import UUID
from datetime import date, datetime, timezone

from pydantic import BaseModel

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from shared.event_models import HospitalEvent, LabEvent, MedicareEvent


def make_message_id(source_patient_id: str, source_system: str, version: int = 1) -> str:
    """Deterministic message ID — sha256(source_patient_id + version + source_system)."""
    raw = f"{source_patient_id}{version}{source_system}{datetime.now(timezone.utc)}"
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
    operation: str                      # "add" | "update" | "remove"
    medicare_id: str                    # shared_identifier — cross-source anchor (MBI equivalent)
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str                         # "M" | "F"
    occurred_at: datetime               # when event occurred (enrollment date)
