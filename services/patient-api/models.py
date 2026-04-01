from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class PatientInfoResponse(BaseModel):
    medicare_id: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None


class TimelineResponse(BaseModel):
    stub: bool = True


class RecommendationResponse(BaseModel):
    stub: bool = True


class RecommendationsResponse(BaseModel):
    stub: bool = True


class ConflictsResponse(BaseModel):
    stub: bool = True


class RecommendationRequest(BaseModel):
    opType: str = ""
    patientId: str = ""
