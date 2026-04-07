from datetime import date, datetime

from pydantic import BaseModel, Field


class PatientIdMapping(BaseModel):
    medicare_id: str | None = None
    canonical_patient_id: str | None = None


class PatientInfoResponse(BaseModel):
    medicare_id: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None


class TimelineResponse(BaseModel):
    id: int | None = Field(None, description="Timeline event ID")
    canonical_patient_id: str | None = Field(None, description="Patient UUID")
    first_name: str | None = Field(None, description="Patient first name")
    last_name: str | None = Field(None, description="Patient last name")
    gender: str | None = Field(None, description="Patient gender (M/F)")
    primary_plan: str | None = Field(None, description="Primary insurance plan")
    member_id: str | None = Field(None, description="Insurance member ID")
    eligibility_status: str | None = Field(None, description="Coverage eligibility status")
    admission_date: datetime | None = Field(None, description="Hospital admission date")
    discharge_date: datetime | None = Field(None, description="Hospital discharge date")
    facility_name: str | None = Field(None, description="Hospital or facility name")
    diagnosis_codes: list[str] | None = Field(None, description="ICD diagnosis codes")
    medications: list[str] | None = Field(None, description="Current medications")
    allergies: list[str] | None = Field(None, description="Known allergies")
    lab_results: list[str] | None = Field(None, description="Recent lab test results")
    created_at: datetime | None = Field(None, description="When this timeline event was created")


class TimelineEventsResponse(BaseModel):
    events: list[TimelineResponse] = Field(default_factory=list, description="List of timeline events")
    page: int = Field(1, description="Current page number (1-indexed)")
    page_size: int = Field(20, description="Number of items per page")
    total_count: int | None = Field(None, description="Total number of timeline events for patient")


class RecommendationResponse(BaseModel):
    id: int | None = Field(None, description="Primary key (DB-generated)")
    summary: str | None = Field(None, description="Recommendation text")
    risk_tier: str | None = Field(None, description="Risk level: high, medium, low")
    generated_at: datetime | None = Field(None, description="When this recommendation was generated")
