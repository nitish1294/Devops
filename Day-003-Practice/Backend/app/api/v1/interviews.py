from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import and_, func, or_, select

from app.api.deps import CurrentUser, Db, ManageJobs
from app.core.enums import InterviewStatus, Stage
from app.models.application import Application
from app.models.interview import Interview, InterviewPanelist
from app.models.user import User
from app.schemas.common import Message, Page
from app.schemas.docs import ScorecardOut
from app.schemas.interview import (
    CandidateBrief,
    FeedbackRequest,
    InterviewCreate,
    InterviewOut,
    InterviewUpdate,
)
from app.core.config import settings
from app.services import activity, calendar, notifications, scorecard

router = APIRouter(prefix="/interviews", tags=["interviews"])


def _decorate(row: Interview) -> InterviewOut:
    out = InterviewOut.model_validate(row)
    if row.application and row.application.candidate:
        out.candidate = CandidateBrief.model_validate(row.application.candidate)
    if row.application and row.application.job:
        out.job_title = row.application.job.title
    return out


async def _load(db, interview_id: int) -> Interview:
    row = (
        (await db.execute(select(Interview).where(Interview.id == interview_id)))
        .unique()
        .scalar_one_or_none()
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Interview not found")
    return row


async def _check_conflicts(
    db, panelist_ids: list[int], start: datetime, minutes: int, exclude_id: int | None = None
) -> list[str]:
    """Refuse to double-book an interviewer. Returns names that clash."""
    if not panelist_ids:
        return []
    end = start + timedelta(minutes=minutes)
    stmt = (
        select(User.full_name, Interview.scheduled_at, Interview.duration_minutes)
        .join(InterviewPanelist, InterviewPanelist.interview_id == Interview.id)
        .join(User, User.id == InterviewPanelist.user_id)
        .where(
            InterviewPanelist.user_id.in_(panelist_ids),
            Interview.status == InterviewStatus.SCHEDULED,
        )
    )
    if exclude_id:
        stmt = stmt.where(Interview.id != exclude_id)

    clashes = []
    for name, other_start, other_minutes in (await db.execute(stmt)).all():
        other_end = other_start + timedelta(minutes=other_minutes)
        if other_start < end and start < other_end:
            clashes.append(name)
    return sorted(set(clashes))


@router.get("", response_model=Page[InterviewOut])
async def list_interviews(
    db: Db,
    _: CurrentUser,
    application_id: int | None = None,
    panelist_id: int | None = None,
    status_filter: InterviewStatus | None = Query(default=None, alias="status"),
    upcoming_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    stmt = select(Interview)
    if application_id:
        stmt = stmt.where(Interview.application_id == application_id)
    if status_filter:
        stmt = stmt.where(Interview.status == status_filter)
    if upcoming_only:
        stmt = stmt.where(Interview.scheduled_at >= datetime.now(timezone.utc))
    if panelist_id:
        stmt = stmt.where(
            Interview.id.in_(
                select(InterviewPanelist.interview_id).where(
                    InterviewPanelist.user_id == panelist_id
                )
            )
        )

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                stmt.order_by(Interview.scheduled_at).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .unique()
        .scalars()
        .all()
    )
    return Page[InterviewOut](
        items=[_decorate(r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.get("/my", response_model=list[InterviewOut])
async def my_interviews(db: Db, actor: CurrentUser):
    """The interviewer's own panel list - what they see when they log in."""
    stmt = (
        select(Interview)
        .where(
            Interview.id.in_(
                select(InterviewPanelist.interview_id).where(InterviewPanelist.user_id == actor.id)
            ),
            Interview.scheduled_at >= datetime.now(timezone.utc) - timedelta(days=1),
        )
        .order_by(Interview.scheduled_at)
    )
    rows = (await db.execute(stmt)).unique().scalars().all()
    return [_decorate(r) for r in rows]


@router.post("", response_model=InterviewOut, status_code=status.HTTP_201_CREATED)
async def schedule_interview(
    payload: InterviewCreate, db: Db, actor: ManageJobs
):
    app_row = (
        (await db.execute(select(Application).where(Application.id == payload.application_id)))
        .unique()
        .scalar_one_or_none()
    )
    if not app_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if app_row.stage in Stage.terminal():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This application is closed. Move it back into the pipeline before scheduling.",
        )
    if payload.scheduled_at <= datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Pick a time in the future")

    clashes = await _check_conflicts(
        db, payload.panelist_ids, payload.scheduled_at, payload.duration_minutes
    )
    if clashes:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Already booked at that time: {', '.join(clashes)}"
        )

    row = Interview(
        application_id=payload.application_id,
        round_name=payload.round_name,
        scheduled_at=payload.scheduled_at,
        duration_minutes=payload.duration_minutes,
        mode=payload.mode,
        location_or_link=payload.location_or_link,
        created_by_id=actor.id,
    )
    db.add(row)
    await db.flush()
    for uid in set(payload.panelist_ids):
        db.add(InterviewPanelist(interview_id=row.id, user_id=uid))

    # Scheduling an interview implies the pipeline has moved on.
    if app_row.stage in (Stage.SOURCED, Stage.SCREENING):
        app_row.stage = Stage.INTERVIEW
        db.add(app_row)

    await db.commit()
    await db.refresh(row)

    await activity.log(
        "interview.schedule",
        "application",
        app_row.id,
        f"{row.round_name} scheduled for {app_row.candidate.full_name}",
        actor.id,
        actor.full_name,
        {"scheduled_at": row.scheduled_at.isoformat()},
    )
    invite = calendar.interview_invite(
        uid=f"interview-{row.id}@hrms",
        summary=f"{row.round_name}: {app_row.job.title}",
        description=(
            f"Interview with {app_row.candidate.full_name} for {app_row.job.title}.\n"
            f"Mode: {row.mode}. Duration: {row.duration_minutes} minutes."
        ),
        starts_at=row.scheduled_at,
        duration_minutes=row.duration_minutes,
        location=row.location_or_link,
        organizer_email=settings.MAIL_FROM,
        attendee_emails=[app_row.candidate.email] + [u.email for u in row.panelist_users],
    )
    await notifications.safe_dispatch(
        "interview_invite",
        app_row.candidate.email,
        {
            "candidate_name": app_row.candidate.full_name,
            "job_title": app_row.job.title,
            "round_name": row.round_name,
            "scheduled_at": row.scheduled_at.strftime("%d %b %Y, %I:%M %p"),
            "location_or_link": row.location_or_link or "To be shared",
        },
        attachments=[
            {
                "filename": "interview.ics",
                "content": invite,
                # text/calendar with METHOD=REQUEST is what makes mail clients
                # offer Accept and Decline rather than showing a file to open.
                "mime": "text/calendar",
            }
        ],
    )
    return _decorate(row)


@router.get("/{interview_id}", response_model=InterviewOut)
async def get_interview(interview_id: int, db: Db, _: CurrentUser):
    return _decorate(await _load(db, interview_id))


@router.patch("/{interview_id}", response_model=InterviewOut)
async def reschedule(
    interview_id: int, payload: InterviewUpdate, db: Db, actor: ManageJobs
):
    row = await _load(db, interview_id)
    data = payload.model_dump(exclude_unset=True)
    panelist_ids = data.pop("panelist_ids", None)

    new_start = data.get("scheduled_at", row.scheduled_at)
    new_minutes = data.get("duration_minutes", row.duration_minutes)
    check_ids = panelist_ids if panelist_ids is not None else [p.user_id for p in row.panelists]
    clashes = await _check_conflicts(db, check_ids, new_start, new_minutes, exclude_id=row.id)
    if clashes:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Already booked at that time: {', '.join(clashes)}"
        )

    for field, value in data.items():
        setattr(row, field, value)
    if panelist_ids is not None:
        for existing in list(row.panelists):
            await db.delete(existing)
        await db.flush()
        for uid in set(panelist_ids):
            db.add(InterviewPanelist(interview_id=row.id, user_id=uid))

    db.add(row)
    await db.commit()
    await db.refresh(row)
    await activity.log(
        "interview.update", "interview", row.id, f"{row.round_name} updated", actor.id, actor.full_name
    )
    return _decorate(row)


@router.post("/{interview_id}/feedback", response_model=ScorecardOut)
async def submit_feedback(interview_id: int, payload: FeedbackRequest, db: Db, actor: CurrentUser):
    """Panelists submit here. Summary goes to Postgres, the scorecard to MongoDB."""
    row = await _load(db, interview_id)
    panel_ids = {p.user_id for p in row.panelists}
    if actor.id not in panel_ids and actor.role not in ("admin", "hr_manager", "recruiter"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only panelists on this interview can submit feedback"
        )

    row.overall_rating = payload.overall_rating
    row.recommendation = payload.recommendation
    row.feedback_summary = payload.feedback_summary
    row.status = InterviewStatus.COMPLETED
    db.add(row)
    await db.commit()

    doc = await scorecard.upsert(
        application_id=row.application_id,
        interview_id=row.id,
        criteria=payload.criteria,
        strengths=payload.strengths,
        concerns=payload.concerns,
        overall_rating=payload.overall_rating,
        recommendation=payload.recommendation,
        submitted_by=actor.id,
    )
    await activity.log(
        "interview.feedback",
        "application",
        row.application_id,
        f"Feedback on {row.round_name}: {payload.recommendation}",
        actor.id,
        actor.full_name,
        {"rating": payload.overall_rating},
    )
    return ScorecardOut(**doc)


@router.post("/{interview_id}/cancel", response_model=Message)
async def cancel(interview_id: int, db: Db, actor: ManageJobs):
    row = await _load(db, interview_id)
    row.status = InterviewStatus.CANCELLED
    db.add(row)
    await db.commit()
    await activity.log(
        "interview.cancel", "interview", row.id, f"{row.round_name} cancelled", actor.id, actor.full_name
    )
    return Message(detail="Interview cancelled")


@router.get("/{interview_id}/invite.ics", response_class=Response)
async def interview_invite_file(interview_id: int, db: Db, _: CurrentUser):
    """The calendar invite for this round, for anyone who needs it again."""
    row = await _load(db, interview_id)
    app_row = row.application
    cancelled = row.status == InterviewStatus.CANCELLED

    content = calendar.interview_invite(
        uid=f"interview-{row.id}@hrms",
        summary=f"{row.round_name}: {app_row.job.title}",
        description=(
            f"Interview with {app_row.candidate.full_name} for {app_row.job.title}.\n"
            f"Mode: {row.mode}. Duration: {row.duration_minutes} minutes."
        ),
        starts_at=row.scheduled_at,
        duration_minutes=row.duration_minutes,
        location=row.location_or_link,
        organizer_email=settings.MAIL_FROM,
        attendee_emails=[app_row.candidate.email] + [u.email for u in row.panelist_users],
        cancelled=cancelled,
        # Bumping the sequence is what tells a calendar client this supersedes
        # the invite it already has.
        sequence=1 if cancelled else 0,
    )
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="interview-{row.id}.ics"'},
    )
