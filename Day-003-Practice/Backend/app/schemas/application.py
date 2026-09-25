from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Stage
from app.schemas.candidate import CandidateOut
from app.schemas.user import UserOut


class ApplicationCreate(BaseModel):
    job_id: int
    candidate_id: int
    stage: Stage = Stage.SOURCED
    owner_id: int | None = None


class StageMoveRequest(BaseModel):
    to_stage: Stage
    note: str | None = None
    rejection_reason: str | None = None
    board_position: int | None = None


class StageEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_stage: str | None
    to_stage: str
    note: str | None
    created_at: datetime
    moved_by: UserOut | None = None


class JobBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    title: str
    location: str | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    stage: Stage
    board_position: int
    match_score: int | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    job: JobBrief
    candidate: CandidateOut
    owner: UserOut | None = None
    interview_count: int = 0
    days_in_stage: int = 0


class ApplicationDetail(ApplicationOut):
    stage_events: list[StageEventOut] = []


class BoardColumn(BaseModel):
    stage: Stage
    label: str
    count: int
    items: list[ApplicationOut]


class Board(BaseModel):
    job_id: int | None
    columns: list[BoardColumn]


class BulkStageRequest(BaseModel):
    """Move several candidates at once — a real screening session rejects in batches."""

    application_ids: list[int] = Field(min_length=1, max_length=200)
    to_stage: Stage
    note: str | None = Field(default=None, max_length=2000)
    rejection_reason: str | None = Field(default=None, max_length=500)


class BulkStageResult(BaseModel):
    moved: int
    skipped: list[dict] = []
