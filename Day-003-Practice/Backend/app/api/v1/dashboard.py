from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Query
from sqlalchemy import Integer, cast, func, select

from app.api.deps import CurrentUser, Db
from app.core.enums import InterviewStatus, JobStatus, OfferStatus, Stage
from app.models.application import Application, StageEvent
from app.models.candidate import Candidate
from app.models.interview import Interview
from app.models.job import Job
from app.models.offer import Offer
from app.schemas.docs import ActivityOut, DashboardStats
from app.services import activity

router = APIRouter(tags=["insights"])


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard(db: Db, _: CurrentUser):
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    open_jobs = (
        await db.execute(select(func.count(Job.id)).where(Job.status == JobStatus.OPEN))
    ).scalar_one()
    total_jobs = (await db.execute(select(func.count(Job.id)))).scalar_one()
    total_candidates = (await db.execute(select(func.count(Candidate.id)))).scalar_one()
    active_applications = (
        await db.execute(
            select(func.count(Application.id)).where(
                Application.stage.notin_(list(Stage.terminal()))
            )
        )
    ).scalar_one()
    interviews_7d = (
        await db.execute(
            select(func.count(Interview.id)).where(
                Interview.scheduled_at.between(now, now + timedelta(days=7)),
                Interview.status == InterviewStatus.SCHEDULED,
            )
        )
    ).scalar_one()
    offers_pending = (
        await db.execute(
            select(func.count(Offer.id)).where(
                Offer.status.in_([OfferStatus.DRAFT, OfferStatus.SENT])
            )
        )
    ).scalar_one()
    hires_this_month = (
        await db.execute(
            select(func.count(Application.id)).where(
                Application.stage == Stage.HIRED, Application.closed_at >= month_start
            )
        )
    ).scalar_one()

    # Average time to hire: first stage event -> hired event, in days.
    first_seen = (
        select(StageEvent.application_id, func.min(StageEvent.created_at).label("started"))
        .group_by(StageEvent.application_id)
        .subquery()
    )
    hired_at = (
        select(StageEvent.application_id, func.max(StageEvent.created_at).label("hired"))
        .where(StageEvent.to_stage == Stage.HIRED)
        .group_by(StageEvent.application_id)
        .subquery()
    )
    avg_days = (
        await db.execute(
            select(
                func.avg(
                    cast(func.extract("epoch", hired_at.c.hired - first_seen.c.started), Integer)
                    / 86400.0
                )
            ).select_from(
                hired_at.join(first_seen, first_seen.c.application_id == hired_at.c.application_id)
            )
        )
    ).scalar_one()

    decided = (
        await db.execute(
            select(Offer.status, func.count(Offer.id))
            .where(Offer.status.in_([OfferStatus.ACCEPTED, OfferStatus.DECLINED]))
            .group_by(Offer.status)
        )
    ).all()
    decided_map = {s: c for s, c in decided}
    accepted = decided_map.get(OfferStatus.ACCEPTED, 0)
    total_decided = sum(decided_map.values())
    acceptance_rate = round(accepted / total_decided * 100, 1) if total_decided else None

    stage_rows = (
        await db.execute(
            select(Application.stage, func.count(Application.id)).group_by(Application.stage)
        )
    ).all()
    pipeline = {s: 0 for s in Stage.board_order()}
    pipeline.update({s: c for s, c in stage_rows})

    source_rows = (
        await db.execute(
            select(Candidate.source, func.count(Candidate.id))
            .group_by(Candidate.source)
            .order_by(func.count(Candidate.id).desc())
        )
    ).all()

    trend_rows = (
        await db.execute(
            select(
                func.to_char(func.date_trunc("month", Application.created_at), "Mon YYYY").label("m"),
                func.date_trunc("month", Application.created_at).label("bucket"),
                func.count(Application.id),
                func.count(Application.id).filter(Application.stage == Stage.HIRED),
            )
            .where(Application.created_at >= now - timedelta(days=180))
            .group_by("m", "bucket")
            .order_by("bucket")
        )
    ).all()

    top_rows = (
        await db.execute(
            select(Job.code, Job.title, func.count(Application.id).label("apps"))
            .join(Application, Application.job_id == Job.id)
            .where(Job.status == JobStatus.OPEN)
            .group_by(Job.id, Job.code, Job.title)
            .order_by(func.count(Application.id).desc())
            .limit(5)
        )
    ).all()

    return DashboardStats(
        open_jobs=open_jobs,
        total_jobs=total_jobs,
        total_candidates=total_candidates,
        active_applications=active_applications,
        interviews_next_7_days=interviews_7d,
        offers_pending=offers_pending,
        hires_this_month=hires_this_month,
        avg_time_to_hire_days=round(float(avg_days), 1) if avg_days else None,
        offer_acceptance_rate=acceptance_rate,
        pipeline_by_stage={str(k): v for k, v in pipeline.items()},
        applications_by_source={(k or "unknown"): v for k, v in source_rows},
        hiring_trend=[
            {"month": m, "applications": apps, "hires": hires} for m, _, apps, hires in trend_rows
        ],
        top_jobs=[{"code": c, "title": t, "applications": a} for c, t, a in top_rows],
    )


@router.get("/activity", response_model=list[ActivityOut])
async def activity_feed(
    _: CurrentUser,
    entity_type: str | None = None,
    entity_id: int | None = None,
    limit: int = Query(50, ge=1, le=200),
):
    return [ActivityOut(**a) for a in await activity.feed(entity_type, entity_id, limit)]
