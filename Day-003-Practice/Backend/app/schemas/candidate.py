from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CandidateBase(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    location: str | None = None
    current_company: str | None = None
    current_title: str | None = None
    total_experience: float | None = Field(default=None, ge=0, le=60)
    current_ctc: float | None = None
    expected_ctc: float | None = None
    notice_period_days: int | None = Field(default=None, ge=0, le=365)
    source: str | None = None
    referred_by: str | None = None
    skills: str | None = None
    linkedin_url: str | None = None


class CandidateCreate(CandidateBase):
    pass


class CandidateUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    location: str | None = None
    current_company: str | None = None
    current_title: str | None = None
    total_experience: float | None = None
    current_ctc: float | None = None
    expected_ctc: float | None = None
    notice_period_days: int | None = None
    source: str | None = None
    referred_by: str | None = None
    skills: str | None = None
    linkedin_url: str | None = None


class CandidateOut(CandidateBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    resume_doc_id: str | None = None
    created_at: datetime
    open_applications: int = 0
