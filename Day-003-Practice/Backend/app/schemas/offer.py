from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import OfferStatus
from app.schemas.interview import CandidateBrief


class OfferCreate(BaseModel):
    application_id: int
    designation: str = Field(min_length=2, max_length=150)
    annual_ctc: float = Field(gt=0)
    fixed_component: float | None = None
    variable_component: float | None = None
    joining_bonus: float | None = None
    joining_date: date | None = None
    valid_till: date | None = None
    notes: str | None = None


class OfferUpdate(BaseModel):
    designation: str | None = None
    annual_ctc: float | None = None
    fixed_component: float | None = None
    variable_component: float | None = None
    joining_bonus: float | None = None
    joining_date: date | None = None
    valid_till: date | None = None
    notes: str | None = None


class OfferStatusUpdate(BaseModel):
    status: OfferStatus
    notes: str | None = None


class OfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    designation: str
    annual_ctc: float
    fixed_component: float | None
    variable_component: float | None
    joining_bonus: float | None
    joining_date: date | None
    valid_till: date | None
    status: OfferStatus
    notes: str | None
    created_at: datetime
    candidate: CandidateBrief | None = None
    job_title: str | None = None
