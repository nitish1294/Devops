from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import InterviewMode, InterviewStatus, Recommendation
from app.schemas.user import UserOut


class InterviewCreate(BaseModel):
    application_id: int
    round_name: str = Field(min_length=2, max_length=120)
    scheduled_at: datetime
    duration_minutes: int = Field(default=45, ge=10, le=480)
    mode: InterviewMode = InterviewMode.VIDEO
    location_or_link: str | None = None
    panelist_ids: list[int] = []


class InterviewUpdate(BaseModel):
    round_name: str | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = None
    mode: InterviewMode | None = None
    location_or_link: str | None = None
    status: InterviewStatus | None = None
    panelist_ids: list[int] | None = None


class FeedbackRequest(BaseModel):
    overall_rating: int = Field(ge=1, le=5)
    recommendation: Recommendation
    feedback_summary: str | None = None
    criteria: dict[str, int] = Field(
        default_factory=dict, description="Free-form per-round criteria, stored in MongoDB"
    )
    strengths: list[str] = []
    concerns: list[str] = []


class CandidateBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: str


class InterviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    round_name: str
    scheduled_at: datetime
    duration_minutes: int
    mode: InterviewMode
    location_or_link: str | None
    status: InterviewStatus
    overall_rating: int | None
    recommendation: str | None
    feedback_summary: str | None
    panelists: list[UserOut] = Field(default_factory=list, validation_alias="panelist_users")
    candidate: CandidateBrief | None = None
    job_title: str | None = None
