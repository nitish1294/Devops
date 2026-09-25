"""Schemas for the MongoDB-backed side of the system."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ResumeOut(BaseModel):
    id: str
    candidate_id: int
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
    parsed: dict[str, Any]
    raw_text_preview: str


class NoteCreate(BaseModel):
    entity_type: str = Field(pattern="^(candidate|application|job)$")
    entity_id: int
    body: str = Field(min_length=1, max_length=4000)


class NoteOut(BaseModel):
    id: str
    entity_type: str
    entity_id: int
    body: str
    author_id: int
    author_name: str
    created_at: datetime


class ActivityOut(BaseModel):
    id: str
    action: str
    entity_type: str
    entity_id: int | None
    summary: str
    actor_id: int | None
    actor_name: str | None
    meta: dict[str, Any] = {}
    created_at: datetime


class ScorecardOut(BaseModel):
    id: str
    application_id: int
    interview_id: int | None
    criteria: dict[str, int]
    strengths: list[str]
    concerns: list[str]
    overall_rating: int | None
    recommendation: str | None
    submitted_by: int | None
    submitted_at: datetime


class EmailTemplateIn(BaseModel):
    code: str = Field(min_length=2, max_length=60)
    name: str
    subject: str
    body: str


class EmailTemplateOut(EmailTemplateIn):
    id: str
    updated_at: datetime
    placeholders: list[str] = []


class SendEmailRequest(BaseModel):
    template_code: str
    candidate_id: int
    context: dict[str, Any] = {}


class DashboardStats(BaseModel):
    open_jobs: int
    total_jobs: int
    total_candidates: int
    active_applications: int
    interviews_next_7_days: int
    offers_pending: int
    hires_this_month: int
    avg_time_to_hire_days: float | None
    offer_acceptance_rate: float | None
    pipeline_by_stage: dict[str, int]
    applications_by_source: dict[str, int]
    hiring_trend: list[dict[str, Any]]
    top_jobs: list[dict[str, Any]]
