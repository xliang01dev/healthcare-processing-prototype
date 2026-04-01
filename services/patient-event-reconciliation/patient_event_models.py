from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, Field


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
    resolution_log: str = Field(description="How conflicts were resolved during reconciliation")
    created_at: datetime = Field(description="When this reconciliation was created")


class PendingPublish(BaseModel):
    """
    Active or historical debounce window state.

    Tracks the range of event_logs [first_event_log_id, last_event_log_id] that belong to each debounce window.
    Active windows have published_at IS NULL. Historical windows have published_at set after reconciliation completes.
    """
    id: int = Field(description="Primary key from pending_publish_debouncer table")
    canonical_patient_id: UUID = Field(description="Patient UUID this debounce window belongs to")
    first_event_log_id: int = Field(description="ID of the first event log in this debounce window (immutable)")
    last_event_log_id: int = Field(description="ID of the last event log in this debounce window (updated as new events arrive)")
    scheduled_after: datetime = Field(description="When this debounce window is eligible for publication (updated on each new event)")
    ceiling_at: datetime = Field(description="Hard deadline for this window (immutable, prevents infinite debounce)")
    published_at: Optional[datetime] = Field(None, description="When this window was published/reconciled (None for active windows)")
    updated_at: datetime = Field(description="When this row was last updated")


class EventLog(BaseModel):
    """
    Durable event log entry from a source system.

    Append-only record of all incoming patient events. This serves as the persistence
    layer since NATS core does not persist messages. If the service restarts or a
    debounce window needs replaying, events can be re-read from this table.
    """
    id: int = Field(description="Primary key from event_logs table")
    canonical_patient_id: UUID = Field(description="Unique identifier for the patient across all source systems")
    source_system_id: int = Field(description="Identifier of the source system that emitted this event")
    message_id: str = Field(description="Unique message ID from the source system for idempotency")
    event_type: str = Field(description="Type of event (e.g., 'enrollment', 'admission', 'lab_result')")
    payload: dict = Field(description="Event payload with event-specific data")
    source_system_occurred_at: datetime = Field(description="Timestamp when the event occurred in the source system")
    created_at: datetime = Field(description="Timestamp when this event was received and logged")
