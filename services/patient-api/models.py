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
    stub: bool = True


class RecommendationResponse(BaseModel):
    id: int | None = Field(None, description="Primary key (DB-generated)")
    summary: str | None = Field(None, description="Recommendation text")
    risk_tier: str | None = Field(None, description="Risk level: high, medium, low")
    generated_at: datetime | None = Field(None, description="When this recommendation was generated")
