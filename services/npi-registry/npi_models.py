from pydantic import BaseModel, Field


class Provider(BaseModel):
    """
    Healthcare provider identified by NPI (National Provider Identifier).

    NPI is a unique 10-digit identifier assigned to all US healthcare providers.
    """
    npi: str = Field(description="National Provider Identifier (10 digits)")
    first_name: str = Field(description="Provider's first name")
    last_name: str = Field(description="Provider's last name")
    title: str = Field(description="Professional credential (MD, DO, OD, OTD, PA, NP, etc.)")
    specialty: str = Field(description="Medical specialty (Cardiology, Orthopedics, Internal Medicine, etc.)")
