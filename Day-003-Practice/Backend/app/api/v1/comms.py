"""Email templates, the send log, and delivery controls — all MongoDB."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, Db, ManageJobs
from app.core.config import settings
from app.models.candidate import Candidate
from app.schemas.docs import EmailTemplateIn, EmailTemplateOut, SendEmailRequest
from app.services import notifications

router = APIRouter(prefix="/comms", tags=["communication"])


@router.get("/templates", response_model=list[EmailTemplateOut])
async def templates(_: CurrentUser):
    out = []
    for t in await notifications.list_templates():
        # The editor needs to know which placeholders the template refers to.
        t["placeholders"] = sorted(
            set(notifications.placeholders(t.get("subject", "")))
            | set(notifications.placeholders(t.get("body", "")))
        )
        out.append(EmailTemplateOut(**t))
    return out


@router.put("/templates", response_model=EmailTemplateOut)
async def save_template(payload: EmailTemplateIn, _: ManageJobs):
    doc = await notifications.save_template(
        payload.code, payload.name, payload.subject, payload.body
    )
    doc["placeholders"] = sorted(
        set(notifications.placeholders(doc.get("subject", "")))
        | set(notifications.placeholders(doc.get("body", "")))
    )
    return EmailTemplateOut(**doc)


@router.post("/preview")
async def preview(payload: SendEmailRequest, db: Db, _: ManageJobs):
    """Render a template against a real candidate without queueing anything.

    Worth having: a template with a typo in a placeholder name renders as the
    literal `$candidat_name`, and you want to see that before it goes out.
    """
    cand = (
        (await db.execute(select(Candidate).where(Candidate.id == payload.candidate_id)))
        .unique()
        .scalar_one_or_none()
    )
    if not cand:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")

    tpl = next(
        (t for t in await notifications.list_templates() if t["code"] == payload.template_code),
        None,
    )
    if not tpl:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown email template")

    context = {"candidate_name": cand.full_name, **payload.context}
    subject = notifications.render(tpl["subject"], context)
    body = notifications.render(tpl["body"], context)
    referenced = set(notifications.placeholders(tpl["subject"])) | set(
        notifications.placeholders(tpl["body"])
    )
    return {
        "to_email": cand.email,
        "subject": subject,
        "body": body,
        "unresolved": sorted(referenced - set(context)),
    }


@router.post("/send", status_code=status.HTTP_202_ACCEPTED)
async def send(payload: SendEmailRequest, db: Db, actor: ManageJobs):
    cand = (
        (await db.execute(select(Candidate).where(Candidate.id == payload.candidate_id)))
        .unique()
        .scalar_one_or_none()
    )
    if not cand:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Candidate not found")
    context = {"candidate_name": cand.full_name, **payload.context}
    try:
        entry = await notifications.dispatch(payload.template_code, cand.email, context)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    return entry


@router.get("/outbox")
async def outbox(
    _: CurrentUser,
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(None, alias="status"),
):
    return await notifications.outbox(limit, status_filter)


@router.get("/mail-status")
async def mail_status(_: CurrentUser):
    """Whether mail is actually going out, and what is waiting.

    Without this the outbox is ambiguous: a queued message looks the same
    whether the worker is off or the mail server is refusing connections.
    """
    counts = {}
    for state in ("queued", "sent", "failed"):
        counts[state] = len(await notifications.outbox(limit=200, status=state))
    return {
        "smtp_configured": settings.smtp_configured,
        "smtp_host": settings.SMTP_HOST or None,
        "worker_enabled": settings.MAIL_WORKER_ENABLED,
        "delivery": "sending" if settings.smtp_configured else "queue only",
        "counts": counts,
    }


@router.post("/outbox/flush")
async def flush(_: ManageJobs, limit: int = Query(25, ge=1, le=100)):
    """Trigger a delivery pass now instead of waiting for the worker."""
    return await notifications.flush_outbox(limit)


@router.post("/outbox/{outbox_id}/retry")
async def retry(outbox_id: str, _: ManageJobs):
    try:
        result = await notifications.retry_message(outbox_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Message not found")
    return {"detail": "Message requeued", **result}
