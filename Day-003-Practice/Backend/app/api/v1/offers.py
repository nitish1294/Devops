from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, Db, ManageOffers
from app.core.enums import OfferStatus, Stage
from app.models.application import Application, StageEvent
from app.models.offer import Offer
from app.schemas.common import Message, Page
from app.schemas.interview import CandidateBrief
from app.schemas.offer import OfferCreate, OfferOut, OfferStatusUpdate, OfferUpdate
from app.services import activity, documents, notifications

router = APIRouter(prefix="/offers", tags=["offers"])

ALLOWED_TRANSITIONS = {
    OfferStatus.DRAFT: {OfferStatus.SENT, OfferStatus.WITHDRAWN},
    OfferStatus.SENT: {OfferStatus.ACCEPTED, OfferStatus.DECLINED, OfferStatus.WITHDRAWN},
    OfferStatus.ACCEPTED: set(),
    OfferStatus.DECLINED: set(),
    OfferStatus.WITHDRAWN: set(),
}



def _letter_bytes(row: Offer, app_row: Application, issued_by: str) -> bytes:
    department = None
    if app_row.job and getattr(app_row.job, "department", None):
        department = app_row.job.department.name
    return documents.offer_letter_pdf(
        candidate_name=app_row.candidate.full_name,
        candidate_email=app_row.candidate.email,
        designation=row.designation,
        department=department,
        annual_ctc=row.annual_ctc,
        fixed_component=row.fixed_component,
        variable_component=row.variable_component,
        joining_bonus=row.joining_bonus,
        joining_date=row.joining_date,
        valid_till=row.valid_till,
        reference=f"OFR-{row.created_at.year}-{row.id:04d}",
        issued_by=issued_by,
    )


def _decorate(row: Offer) -> OfferOut:
    out = OfferOut.model_validate(row)
    if row.application and row.application.candidate:
        out.candidate = CandidateBrief.model_validate(row.application.candidate)
    if row.application and row.application.job:
        out.job_title = row.application.job.title
    return out


async def _load(db, offer_id: int) -> Offer:
    row = (
        (await db.execute(select(Offer).where(Offer.id == offer_id))).unique().scalar_one_or_none()
    )
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Offer not found")
    return row


@router.get("", response_model=Page[OfferOut])
async def list_offers(
    db: Db,
    _: CurrentUser,
    status_filter: OfferStatus | None = Query(default=None, alias="status"),
    application_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    stmt = select(Offer)
    if status_filter:
        stmt = stmt.where(Offer.status == status_filter)
    if application_id:
        stmt = stmt.where(Offer.application_id == application_id)

    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                stmt.order_by(Offer.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
            )
        )
        .unique()
        .scalars()
        .all()
    )
    return Page[OfferOut](
        items=[_decorate(r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.post("", response_model=OfferOut, status_code=status.HTTP_201_CREATED)
async def create_offer(payload: OfferCreate, db: Db, actor: ManageOffers):
    app_row = (
        (await db.execute(select(Application).where(Application.id == payload.application_id)))
        .unique()
        .scalar_one_or_none()
    )
    if not app_row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")

    live = (
        await db.execute(
            select(Offer.id).where(
                Offer.application_id == payload.application_id,
                Offer.status.in_([OfferStatus.DRAFT, OfferStatus.SENT, OfferStatus.ACCEPTED]),
            )
        )
    ).scalar_one_or_none()
    if live:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "There is already a live offer on this application. Withdraw it before raising another.",
        )

    fixed = payload.fixed_component
    variable = payload.variable_component
    if fixed is not None and variable is not None and fixed + variable > payload.annual_ctc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Fixed plus variable cannot exceed the annual CTC"
        )

    row = Offer(**payload.model_dump(), approved_by_id=actor.id)
    db.add(row)

    if app_row.stage != Stage.OFFER:
        db.add(
            StageEvent(
                application_id=app_row.id,
                from_stage=app_row.stage,
                to_stage=Stage.OFFER,
                note="Offer raised",
                moved_by_id=actor.id,
            )
        )
        app_row.stage = Stage.OFFER
        db.add(app_row)

    await db.commit()
    await db.refresh(row)
    await activity.log(
        "offer.create",
        "application",
        app_row.id,
        f"Offer drafted for {app_row.candidate.full_name}",
        actor.id,
        actor.full_name,
        {"annual_ctc": float(payload.annual_ctc)},
    )
    return _decorate(row)


@router.get("/{offer_id}", response_model=OfferOut)
async def get_offer(offer_id: int, db: Db, _: CurrentUser):
    return _decorate(await _load(db, offer_id))


@router.patch("/{offer_id}", response_model=OfferOut)
async def update_offer(
    offer_id: int, payload: OfferUpdate, db: Db, actor: ManageOffers
):
    row = await _load(db, offer_id)
    if row.status != OfferStatus.DRAFT:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only draft offers can be edited. Withdraw and raise a new one."
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(row, field, value)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    await activity.log(
        "offer.update", "offer", row.id, "Offer revised", actor.id, actor.full_name
    )
    return _decorate(row)


@router.post("/{offer_id}/status", response_model=OfferOut)
async def change_status(
    offer_id: int, payload: OfferStatusUpdate, db: Db, actor: ManageOffers
):
    """Offer lifecycle. Accepting an offer marks the candidate hired."""
    row = await _load(db, offer_id)
    current = OfferStatus(row.status)
    if payload.status not in ALLOWED_TRANSITIONS[current]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Cannot move an offer from {current} to {payload.status}"
        )

    row.status = payload.status
    if payload.notes:
        row.notes = payload.notes
    db.add(row)

    app_row = row.application
    if payload.status == OfferStatus.ACCEPTED and app_row.stage != Stage.HIRED:
        db.add(
            StageEvent(
                application_id=app_row.id,
                from_stage=app_row.stage,
                to_stage=Stage.HIRED,
                note="Offer accepted",
                moved_by_id=actor.id,
            )
        )
        app_row.stage = Stage.HIRED
        db.add(app_row)
    elif payload.status == OfferStatus.DECLINED:
        db.add(
            StageEvent(
                application_id=app_row.id,
                from_stage=app_row.stage,
                to_stage=Stage.REJECTED,
                note="Offer declined by candidate",
                moved_by_id=actor.id,
            )
        )
        app_row.stage = Stage.REJECTED
        app_row.rejection_reason = "Offer declined by candidate"
        db.add(app_row)

    await db.commit()
    await db.refresh(row)

    if payload.status == OfferStatus.SENT:
        await notifications.safe_dispatch(
            "offer_released",
            app_row.candidate.email,
            {"candidate_name": app_row.candidate.full_name, "designation": row.designation},
            attachments=[
                {
                    "filename": f"Offer letter - {app_row.candidate.full_name}.pdf",
                    "content": _letter_bytes(row, app_row, actor.full_name),
                    "mime": "application/pdf",
                }
            ],
        )
    await activity.log(
        "offer.status",
        "application",
        app_row.id,
        f"Offer {payload.status} for {app_row.candidate.full_name}",
        actor.id,
        actor.full_name,
    )
    return _decorate(row)


@router.delete("/{offer_id}", response_model=Message)
async def delete_draft(offer_id: int, db: Db, actor: ManageOffers):
    row = await _load(db, offer_id)
    if row.status != OfferStatus.DRAFT:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only draft offers can be deleted")
    await db.delete(row)
    await db.commit()
    await activity.log("offer.delete", "offer", offer_id, "Draft offer deleted", actor.id, actor.full_name)
    return Message(detail="Draft offer deleted")


@router.get("/{offer_id}/letter.pdf", response_class=Response)
async def offer_letter(offer_id: int, db: Db, actor: ManageOffers):
    """The formal offer letter as a PDF.

    Generated on demand rather than stored, so it always reflects the current
    figures — an offer edited while still in draft cannot leave a stale letter
    lying around.
    """
    row = await _load(db, offer_id)
    pdf = _letter_bytes(row, row.application, actor.full_name)
    safe_name = "".join(
        ch if ch.isalnum() or ch in " -_" else "-"
        for ch in row.application.candidate.full_name
    ).strip() or f"offer-{offer_id}"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="Offer letter - {safe_name}.pdf"'},
    )
