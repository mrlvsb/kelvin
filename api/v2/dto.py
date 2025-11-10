from ninja import Schema
from pydantic import Field


class SemesterResponse(Schema):
    pk: int = Field(..., description="Primary key of the semester")
    year: int = Field(..., description="Year of the semester")
    winter: bool = Field(..., description="Is it a winter semester?")
    inbus_semester_id: int = Field(..., description="ID of the INBUS semester")
