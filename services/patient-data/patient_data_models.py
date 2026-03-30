from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from shared.event_models import HospitalEvent, LabEvent, MedicareEvent

# ---------------------------------------------------------------------------
# patient.hydrate
# ---------------------------------------------------------------------------

class GoldenRecord(BaseModel):
    canonical_patient_id: UUID
    source_system_ids: list[int]
    given_name: str | None
    family_name: str | None
    date_of_birth: date | None
    gender: str | None
    record_version: int = 1  # Database increments on update
    last_reconciled_at: datetime | None = None  # Database sets to NOW() on upsert


class SourceSystem(BaseModel):
    source_system_id: int
    source_system_name: str


class SourceIdentity(BaseModel):
    id: int
    canonical_patient_id: UUID
    source_system_id: int
    source_patient_id: str
    created_at: datetime


class HydrateEvent(BaseModel):
    operation: str          # "add" | "update" | "remove"
    medicare_id: str        # shared_identifier — cross-source anchor (MBI equivalent)
    first_name: str
    last_name: str
    date_of_birth: date
    gender: str             # "M" | "F"


# Re-export shared event models for convenience
__all__ = [
    "GoldenRecord",
    "HospitalEvent",
    "HydrateEvent",
    "LabEvent",
    "MedicareEvent",
    "SourceIdentity",
    "SourceSystem",
]
