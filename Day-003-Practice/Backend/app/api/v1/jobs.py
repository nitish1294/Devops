from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, Db, ManageJobs
from app.core.enums import JobStatus, Stage
from app.models.application import Application
from app.models.job import Job
from app.schemas.common import Message, Page
from app.schemas.job import JobCreate, JobOut, JobUpdate
from app.services import activity

router = APIRouter(prefix="/jobs", tags=["jobs"])


async def _generate_code(db: Db) -> str:
    year = datetime.now(timezone.utc).year
    count = (await db.execute(select(func.count(Job.id)))).scalar_one()
    return f"REQ-{year}-{count + 1:04d}"


async def _decorate(db, job: Job) -> JobOut:
    total = (
        await db.execute(select(func.count(Application.id)).where(Application.job_id == job.id))
    ).scalar_one()
    hired = (
        await db.execute(
            select(func.count(Application.id)).where(
                Application.job_id == job.id, Application.stage == Stage.HIRED
            )
        )
    ).scalar_one()
    out = JobOut.model_validate(job)
    out.applicant_count = total
    out.hired_count = hired
    return out


@router.get("", response_model=Page[JobOut])
async def list_jobs(
    db: Db,
    _: CurrentUser,
    q: str | None = None,
    status_filter: JobStatus | None = Query(default=None, alias="status"),
    department_id: int | None = None,
    recruiter_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = select(Job)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(
            func.lower(Job.title).like(like)
            | func.lower(Job.code).like(like)
            | func.lower(func.coalesce(Job.skills, "")).like(like)
        )
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    if department_id:
        stmt = stmt.where(Job.department_id == department_id)
    if recruiter_id:
        stmt = stmt.where(Job.recruiter_id == recruiter_id)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                stmt.order_by(Job.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .unique()
        .scalars()
        .all()
    )
    return Page[JobOut](
        items=[await _decorate(db, r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(payload: JobCreate, db: Db, actor: ManageJobs):
    data = payload.model_dump()
    code = (data.pop("code", None) or "").strip() or await _generate_code(db)
    clash = (await db.execute(select(Job.id).where(Job.code == code))).scalar_one_or_none()
    if clash:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Requisition code {code} is already in use")

    job = Job(**data, code=code)
    if job.recruiter_id is None:
        job.recruiter_id = actor.id
    db.add(job)
    await db.commit()
    await db.refresh(job)
    await activity.log(
        "job.create", "job", job.id, f"Opened requisition {job.code} - {job.title}", actor.id, actor.full_name
    )
    return await _decorate(db, job)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: int, db: Db, _: CurrentUser):
    job = (await db.execute(select(Job).where(Job.id == job_id))).unique().scalar_one_or_none()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Requisition not found")
    return await _decorate(db, job)


@router.patch("/{job_id}", response_model=JobOut)
async def update_job(
    job_id: int, payload: JobUpdate, db: Db, actor: ManageJobs
):
    job = (await db.execute(select(Job).where(Job.id == job_id))).unique().scalar_one_or_none()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Requisition not found")

    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(job, field, value)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    await activity.log(
        "job.update",
        "job",
        job.id,
        f"Updated {job.code}",
        actor.id,
        actor.full_name,
        {"fields": list(changes.keys())},
    )
    return await _decorate(db, job)


@router.delete("/{job_id}", response_model=Message)
async def close_job(job_id: int, db: Db, actor: ManageJobs):
    """Requisitions are closed, never hard deleted - the applications must survive."""
    job = (await db.execute(select(Job).where(Job.id == job_id))).unique().scalar_one_or_none()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Requisition not found")
    job.status = JobStatus.CLOSED
    db.add(job)
    await db.commit()
    await activity.log(
        "job.close", "job", job.id, f"Closed {job.code}", actor.id, actor.full_name
    )
    return Message(detail=f"{job.code} closed")
