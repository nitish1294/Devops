from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, Db, ManageJobs, MovePipeline
from app.core.enums import Stage
from app.models.application import Application, StageEvent
from app.models.candidate import Candidate
from app.models.job import Job
from app.schemas.application import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationOut,
    Board,
    BoardColumn,
    BulkStageRequest,
    BulkStageResult,
    StageEventOut,
    StageMoveRequest,
)
from app.schemas.common import Message, Page
from app.schemas.docs import ScorecardOut
from app.services import activity, export, notifications, resume, scorecard

router = APIRouter(prefix="/applications", tags=["pipeline"])

STAGE_LABELS = {
    Stage.SOURCED: "Sourced",
    Stage.SCREENING: "Screening",
    Stage.INTERVIEW: "Interview",
    Stage.ASSESSMENT: "Assessment",
    Stage.OFFER: "Offer",
    Stage.HIRED: "Hired",
    Stage.REJECTED: "Rejected",
}


def _decorate(app_row: Application) -> ApplicationOut:
    out = ApplicationOut.model_validate(app_row)
    out.interview_count = len(app_row.interviews or [])
    reference = app_row.updated_at or app_row.created_at
    if reference:
        out.days_in_stage = max(0, (datetime.now(timezone.utc) - reference).days)
    return out


async def _load(db, application_id: int) -> Application:
    row = (
        (await db.execute(select(Application).where(Application.id == application_id)))
        .unique()
        .scalar_one_or_none()
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return row


@router.get("", response_model=Page[ApplicationOut])
async def list_applications(
    db: Db,
    _: CurrentUser,
    job_id: int | None = None,
    candidate_id: int | None = None,
    stage: Stage | None = None,
    owner_id: int | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    stmt = select(Application)
    if job_id:
        stmt = stmt.where(Application.job_id == job_id)
    if candidate_id:
        stmt = stmt.where(Application.candidate_id == candidate_id)
    if stage:
        stmt = stmt.where(Application.stage == stage)
    if owner_id:
        stmt = stmt.where(Application.owner_id == owner_id)
    if q:
        stmt = stmt.join(Candidate, Candidate.id == Application.candidate_id).where(
            func.lower(Candidate.full_name).like(f"%{q.lower()}%")
        )

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                stmt.order_by(Application.updated_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        .unique()
        .scalars()
        .all()
    )
    return Page[ApplicationOut](
        items=[_decorate(r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.get("/board", response_model=Board)
async def pipeline_board(db: Db, _: CurrentUser, job_id: int | None = None):
    """Everything the kanban needs in one round trip."""
    stmt = select(Application)
    if job_id:
        stmt = stmt.where(Application.job_id == job_id)
    rows = (
        (await db.execute(stmt.order_by(Application.board_position, Application.id)))
        .unique()
        .scalars()
        .all()
    )

    grouped: dict[str, list[ApplicationOut]] = {s: [] for s in Stage.board_order()}
    for row in rows:
        grouped.setdefault(row.stage, []).append(_decorate(row))

    columns = [
        BoardColumn(
            stage=stage,
            label=STAGE_LABELS[stage],
            count=len(grouped.get(stage, [])),
            items=grouped.get(stage, []),
        )
        for stage in Stage.board_order()
    ]
    return Board(job_id=job_id, columns=columns)


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
async def create_application(
    payload: ApplicationCreate, db: Db, actor: ManageJobs
):
    job = (
        (await db.execute(select(Job).where(Job.id == payload.job_id))).unique().scalar_one_or_none()
    )
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Requisition not found")
    cand = (
        (await db.execute(select(Candidate).where(Candidate.id == payload.candidate_id)))
        .unique()
        .scalar_one_or_none()
    )
    if not cand:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")

    duplicate = (
        await db.execute(
            select(Application.id).where(
                Application.job_id == payload.job_id,
                Application.candidate_id == payload.candidate_id,
            )
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"{cand.full_name} is already in the pipeline for {job.code}"
        )

    tail = (
        await db.execute(
            select(func.coalesce(func.max(Application.board_position), 0)).where(
                Application.job_id == payload.job_id, Application.stage == payload.stage
            )
        )
    ).scalar_one()

    app_row = Application(
        job_id=payload.job_id,
        candidate_id=payload.candidate_id,
        stage=payload.stage,
        owner_id=payload.owner_id or job.recruiter_id or actor.id,
        board_position=tail + 1,
        match_score=resume.score_match(job.skill_list, cand.skill_list),
    )
    db.add(app_row)
    await db.flush()
    db.add(
        StageEvent(
            application_id=app_row.id,
            from_stage=None,
            to_stage=payload.stage,
            note="Added to pipeline",
            moved_by_id=actor.id,
            created_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    await db.refresh(app_row)

    await activity.log(
        "application.create",
        "application",
        app_row.id,
        f"{cand.full_name} added to {job.code}",
        actor.id,
        actor.full_name,
        {"match_score": app_row.match_score},
    )
    await notifications.safe_dispatch(
        "application_received",
        cand.email,
        {"candidate_name": cand.full_name, "job_title": job.title},
    )
    return _decorate(app_row)


@router.get("/{application_id}", response_model=ApplicationDetail)
async def get_application(application_id: int, db: Db, _: CurrentUser):
    row = await _load(db, application_id)
    detail = ApplicationDetail.model_validate(row)
    detail.interview_count = len(row.interviews or [])
    detail.stage_events = [StageEventOut.model_validate(e) for e in row.stage_events]
    return detail


# Registered before /{application_id}/stage: FastAPI matches routes in
# declaration order, and "bulk" would otherwise be read as an id.
@router.post("/bulk/stage", response_model=BulkStageResult)
async def bulk_move_stage(payload: BulkStageRequest, db: Db, actor: MovePipeline):
    """Move a batch through the pipeline in one transaction.

    Rows that cannot legally move are reported back rather than failing the
    whole call — one already-rejected candidate in a selection of thirty should
    not undo the other twenty-nine.
    """
    if payload.to_stage == Stage.REJECTED and not payload.rejection_reason:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add a reason before rejecting")

    rows = (
        (
            await db.execute(
                select(Application)
                .where(Application.id.in_(payload.application_ids))
                .options(
                    selectinload(Application.candidate),
                    selectinload(Application.job),
                )
            )
        )
        .unique()
        .scalars()
        .all()
    )
    found = {r.id for r in rows}
    skipped = [
        {"application_id": i, "reason": "Not found"}
        for i in payload.application_ids
        if i not in found
    ]

    now = datetime.now(timezone.utc)
    moved: list[Application] = []

    for row in rows:
        if row.stage == payload.to_stage:
            skipped.append(
                {
                    "application_id": row.id,
                    "candidate": row.candidate.full_name,
                    "reason": f"Already in {STAGE_LABELS[row.stage]}",
                }
            )
            continue

        previous = row.stage
        tail = (
            await db.execute(
                select(func.coalesce(func.max(Application.board_position), 0)).where(
                    Application.job_id == row.job_id,
                    Application.stage == payload.to_stage,
                )
            )
        ).scalar_one()

        row.stage = payload.to_stage
        row.board_position = tail + 1
        if payload.to_stage == Stage.REJECTED:
            row.rejection_reason = payload.rejection_reason
        if payload.to_stage in Stage.terminal():
            row.closed_at = now
        else:
            row.closed_at = None
            row.rejection_reason = None

        db.add(row)
        db.add(
            StageEvent(
                application_id=row.id,
                from_stage=previous,
                to_stage=payload.to_stage,
                note=payload.note or payload.rejection_reason,
                moved_by_id=actor.id,
                created_at=now,
            )
        )
        moved.append(row)

    await db.commit()

    for row in moved:
        await activity.log(
            "application.stage",
            "application",
            row.id,
            f"{row.candidate.full_name} moved to {STAGE_LABELS[payload.to_stage]} (bulk)",
            actor.id,
            actor.full_name,
            {"to": str(payload.to_stage), "bulk": True},
        )
        if payload.to_stage == Stage.REJECTED:
            await notifications.safe_dispatch(
                "regret",
                row.candidate.email,
                {"candidate_name": row.candidate.full_name, "job_title": row.job.title},
            )

    return BulkStageResult(moved=len(moved), skipped=skipped)

@router.post("/{application_id}/stage", response_model=ApplicationOut)
async def move_stage(
    application_id: int,
    payload: StageMoveRequest,
    db: Db,
    actor: MovePipeline,
):
    """The single write path for stage changes - drag/drop and buttons both land here."""
    row = await _load(db, application_id)
    previous = row.stage

    if previous == payload.to_stage and payload.board_position is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Already in {STAGE_LABELS[previous]}")
    if payload.to_stage == Stage.REJECTED and not payload.rejection_reason:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add a reason before rejecting")

    row.stage = payload.to_stage
    if payload.board_position is not None:
        row.board_position = payload.board_position
    else:
        tail = (
            await db.execute(
                select(func.coalesce(func.max(Application.board_position), 0)).where(
                    Application.job_id == row.job_id, Application.stage == payload.to_stage
                )
            )
        ).scalar_one()
        row.board_position = tail + 1

    if payload.to_stage == Stage.REJECTED:
        row.rejection_reason = payload.rejection_reason
    if payload.to_stage in Stage.terminal():
        row.closed_at = datetime.now(timezone.utc)
    else:
        row.closed_at = None
        row.rejection_reason = None

    db.add(row)
    db.add(
        StageEvent(
            application_id=row.id,
            from_stage=previous,
            to_stage=payload.to_stage,
            note=payload.note or payload.rejection_reason,
            moved_by_id=actor.id,
            created_at=datetime.now(timezone.utc),
        )
    )
    await db.commit()
    await db.refresh(row)

    await activity.log(
        "application.stage",
        "application",
        row.id,
        f"{row.candidate.full_name}: {STAGE_LABELS[previous]} to {STAGE_LABELS[payload.to_stage]}",
        actor.id,
        actor.full_name,
        {"from": previous, "to": str(payload.to_stage)},
    )
    if payload.to_stage == Stage.REJECTED:
        await notifications.safe_dispatch(
            "regret",
            row.candidate.email,
            {"candidate_name": row.candidate.full_name, "job_title": row.job.title},
        )
    return _decorate(row)


@router.patch("/{application_id}/owner", response_model=ApplicationOut)
async def reassign(
    application_id: int,
    body: dict,
    db: Db,
    actor: ManageJobs,
):
    row = await _load(db, application_id)
    row.owner_id = body.get("owner_id")
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await activity.log(
        "application.reassign", "application", row.id, "Owner changed", actor.id, actor.full_name
    )
    return _decorate(row)


@router.get("/{application_id}/scorecards", response_model=list[ScorecardOut])
async def application_scorecards(application_id: int, db: Db, _: CurrentUser):
    await _load(db, application_id)
    return [ScorecardOut(**s) for s in await scorecard.for_application(application_id)]


@router.delete("/{application_id}", response_model=Message)
async def withdraw(application_id: int, db: Db, actor: ManageJobs):
    row = await _load(db, application_id)
    name = row.candidate.full_name
    await db.delete(row)
    await db.commit()
    await activity.log(
        "application.delete", "application", application_id, f"Removed {name} from pipeline", actor.id, actor.full_name
    )
    return Message(detail=f"{name} removed from the pipeline")


@router.get("/export/csv", response_class=Response)
async def export_pipeline(
    db: Db,
    _: CurrentUser,
    job_id: int | None = None,
    stage: Stage | None = None,
):
    """The pipeline as a spreadsheet, for status meetings and offline review."""
    stmt = (
        select(Application)
        .options(
            selectinload(Application.candidate),
            selectinload(Application.job),
            selectinload(Application.owner),
        )
        .order_by(Application.created_at.desc())
    )
    if job_id:
        stmt = stmt.where(Application.job_id == job_id)
    if stage:
        stmt = stmt.where(Application.stage == stage)

    rows = (await db.execute(stmt)).unique().scalars().all()
    headers = [
        "Candidate", "Email", "Phone", "Requisition", "Requisition code", "Stage",
        "Match score", "Owner", "Source", "Applied on", "Rejection reason",
    ]
    data = [
        [
            r.candidate.full_name, r.candidate.email, r.candidate.phone,
            r.job.title, r.job.code, STAGE_LABELS[r.stage], r.match_score,
            r.owner.full_name if r.owner else None,
            r.candidate.source, r.created_at, r.rejection_reason,
        ]
        for r in rows
    ]
    return Response(
        content=export.to_csv(headers, data),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{export.filename("pipeline")}"'
        },
    )
