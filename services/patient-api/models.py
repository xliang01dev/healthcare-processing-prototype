from pydantic import BaseModel


class PatientInfoResponse(BaseModel):
    stub: bool = True


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
