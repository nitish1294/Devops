"""Candidate email: templates, rendering, an outbox, and actual delivery.

The outbox is the source of truth. `dispatch` only ever writes a row; a
background worker picks queued rows up and hands them to SMTP. That split is
deliberate — a slow or down mail server must never make scheduling an interview
fail, and every message stays auditable whether or not it went out.

With SMTP_HOST unset nothing is sent and rows sit at `queued`, which is the
right behaviour on a staging box that should not mail real candidates.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid
from string import Template

from bson import ObjectId

from app.core.config import settings
from app.db.mongo import get_mongo

log = logging.getLogger("hrms.mail")

DEFAULT_TEMPLATES = [
    {
        "code": "application_received",
        "name": "Application received",
        "subject": "We have your application for $job_title",
        "body": "Hi $candidate_name,\n\nThanks for applying to $job_title. "
        "Our team is reviewing your profile and will be in touch shortly.\n\n- Talent team",
    },
    {
        "code": "interview_invite",
        "name": "Interview invite",
        "subject": "Interview scheduled: $job_title",
        "body": "Hi $candidate_name,\n\nYour $round_name for $job_title is set for "
        "$scheduled_at. Joining details: $location_or_link\n\n- Talent team",
    },
    {
        "code": "interview_reminder",
        "name": "Interview reminder",
        "subject": "Reminder: your $round_name tomorrow",
        "body": "Hi $candidate_name,\n\nA quick reminder about your $round_name for "
        "$job_title on $scheduled_at.\n\nJoining details: $location_or_link\n\n- Talent team",
    },
    {
        "code": "offer_released",
        "name": "Offer released",
        "subject": "Your offer for $designation",
        "body": "Hi $candidate_name,\n\nWe are delighted to offer you the role of "
        "$designation. The formal letter is attached.\n\n- Talent team",
    },
    {
        "code": "regret",
        "name": "Regret note",
        "subject": "Update on your application for $job_title",
        "body": "Hi $candidate_name,\n\nAfter careful review we are not moving ahead for "
        "$job_title this time. We would like to stay in touch for future roles.\n\n- Talent team",
    },
]


async def seed_templates() -> None:
    db = get_mongo()
    for tpl in DEFAULT_TEMPLATES:
        await db.email_templates.update_one(
            {"code": tpl["code"]},
            {"$setOnInsert": {**tpl, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )


async def list_templates() -> list[dict]:
    out = []
    async for doc in get_mongo().email_templates.find().sort("name", 1):
        doc["id"] = str(doc.pop("_id"))
        out.append(doc)
    return out


async def save_template(code: str, name: str, subject: str, body: str) -> dict:
    await get_mongo().email_templates.update_one(
        {"code": code},
        {
            "$set": {
                "code": code,
                "name": name,
                "subject": subject,
                "body": body,
                "updated_at": datetime.now(timezone.utc),
            }
        },
        upsert=True,
    )
    doc = await get_mongo().email_templates.find_one({"code": code})
    doc["id"] = str(doc.pop("_id"))
    return doc


def render(text: str, context: dict) -> str:
    return Template(text).safe_substitute(context)


def placeholders(text: str) -> list[str]:
    """Every $name the template refers to, so the UI can list them."""
    found: list[str] = []
    for match in Template.pattern.finditer(text):
        name = match.group("named") or match.group("braced")
        if name and name not in found:
            found.append(name)
    return found


async def dispatch(
    template_code: str,
    to_email: str,
    context: dict,
    attachments: list[dict] | None = None,
) -> dict:
    """Render a template and queue it. Returns the outbox row.

    `attachments` entries are {"filename", "content" (bytes), "mime"}.
    """
    tpl = await get_mongo().email_templates.find_one({"code": template_code})
    if not tpl:
        raise ValueError(f"Unknown email template: {template_code}")

    entry = {
        "template_code": template_code,
        "to_email": to_email,
        "subject": render(tpl["subject"], context),
        "body": render(tpl["body"], context),
        "context": context,
        "attachments": attachments or [],
        "status": "queued",
        "attempts": 0,
        "last_error": None,
        "sent_at": None,
        "created_at": datetime.now(timezone.utc),
    }
    res = await get_mongo().outbox.insert_one(entry)
    entry["id"] = str(res.inserted_id)
    entry.pop("_id", None)
    log.info(
        "queued mail",
        extra={"template": template_code, "to": to_email, "outbox_id": entry["id"]},
    )
    return entry


async def safe_dispatch(
    template_code: str,
    to_email: str,
    context: dict,
    attachments: list[dict] | None = None,
) -> dict | None:
    """dispatch, but a mail problem can never fail the caller.

    Every notification in this system is a side effect of something that has
    already been committed — a stage move, a scheduled interview, a released
    offer. If the template is missing or Mongo hiccups, the right outcome is a
    logged error, not a 500 on an operation that actually succeeded.
    """
    try:
        return await dispatch(template_code, to_email, context, attachments)
    except Exception as exc:
        log.error(
            "could not queue mail",
            extra={
                "template": template_code,
                "to": to_email,
                "error": f"{type(exc).__name__}: {exc}"[:300],
            },
        )
        return None


async def outbox(limit: int = 50, status: str | None = None) -> list[dict]:
    query = {"status": status} if status else {}
    out = []
    async for doc in get_mongo().outbox.find(query).sort("created_at", -1).limit(limit):
        doc["id"] = str(doc.pop("_id"))
        # Attachment bytes would bloat the response and mean nothing to the UI.
        doc["attachments"] = [
            {"filename": a.get("filename"), "mime": a.get("mime")}
            for a in doc.get("attachments", [])
        ]
        out.append(doc)
    return out


def _build_message(row: dict) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = formataddr((settings.MAIL_FROM_NAME, settings.MAIL_FROM))
    msg["To"] = row["to_email"]
    msg["Subject"] = row["subject"]
    msg["Message-ID"] = make_msgid()
    msg.set_content(row["body"])

    for att in row.get("attachments") or []:
        content = att.get("content")
        if not content:
            continue
        maintype, _, subtype = (att.get("mime") or "application/octet-stream").partition("/")
        msg.add_attachment(
            content,
            maintype=maintype,
            subtype=subtype or "octet-stream",
            filename=att.get("filename", "attachment"),
        )
    return msg


def _send_sync(msg: EmailMessage) -> None:
    """Blocking SMTP send. Called in a thread so the event loop keeps running."""
    if settings.SMTP_PORT == 465:
        client = smtplib.SMTP_SSL(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT,
            context=ssl.create_default_context(),
        )
    else:
        client = smtplib.SMTP(
            settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.SMTP_TIMEOUT
        )
    try:
        client.ehlo()
        if settings.SMTP_STARTTLS and settings.SMTP_PORT != 465:
            client.starttls(context=ssl.create_default_context())
            client.ehlo()
        if settings.SMTP_USER:
            client.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        client.send_message(msg)
    finally:
        try:
            client.quit()
        except Exception:
            client.close()


async def deliver_one(row: dict) -> bool:
    """Attempt delivery of a single outbox row and record the outcome."""
    db = get_mongo()
    oid = row["_id"]
    attempts = int(row.get("attempts", 0)) + 1

    try:
        await asyncio.to_thread(_send_sync, _build_message(row))
    except Exception as exc:
        permanent = attempts >= settings.MAIL_MAX_ATTEMPTS
        await db.outbox.update_one(
            {"_id": oid},
            {
                "$set": {
                    "status": "failed" if permanent else "queued",
                    "attempts": attempts,
                    "last_error": f"{type(exc).__name__}: {exc}"[:500],
                    # Back off so a broken server is not hammered every cycle.
                    "retry_after": datetime.now(timezone.utc)
                    + timedelta(seconds=min(600, 30 * 2 ** (attempts - 1))),
                }
            },
        )
        log.warning(
            "mail delivery failed",
            extra={
                "outbox_id": str(oid),
                "attempt": attempts,
                "permanent": permanent,
                "error": str(exc)[:200],
            },
        )
        return False

    await db.outbox.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": "sent",
                "attempts": attempts,
                "last_error": None,
                "sent_at": datetime.now(timezone.utc),
            },
            # Delivered: the bytes have served their purpose.
            "$unset": {"attachments": "", "retry_after": ""},
        },
    )
    log.info("mail sent", extra={"outbox_id": str(oid), "to": row.get("to_email")})
    return True


async def flush_outbox(limit: int = 25) -> dict:
    """Deliver what is due. Returns a small summary; safe to call by hand."""
    if not settings.smtp_configured:
        return {"sent": 0, "failed": 0, "skipped": "SMTP is not configured"}

    now = datetime.now(timezone.utc)
    query = {
        "status": "queued",
        "$or": [{"retry_after": {"$exists": False}}, {"retry_after": {"$lte": now}}],
    }
    sent = failed = 0
    async for row in get_mongo().outbox.find(query).sort("created_at", 1).limit(limit):
        if await deliver_one(row):
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "failed": failed}


async def retry_message(outbox_id: str) -> dict:
    """Put a failed message back in the queue."""
    db = get_mongo()
    res = await db.outbox.update_one(
        {"_id": ObjectId(outbox_id)},
        {"$set": {"status": "queued", "attempts": 0, "last_error": None},
         "$unset": {"retry_after": ""}},
    )
    if not res.matched_count:
        raise ValueError("No such message")
    return await flush_outbox(limit=1)


async def outbox_worker(stop: asyncio.Event) -> None:
    """Background loop started at app startup and cancelled at shutdown."""
    if not settings.smtp_configured:
        log.info("mail worker idle: SMTP_HOST is not set, messages stay queued")
        return

    log.info("mail worker started", extra={"interval": settings.MAIL_WORKER_INTERVAL})
    while not stop.is_set():
        try:
            result = await flush_outbox()
            if result.get("sent") or result.get("failed"):
                log.info("outbox flushed", extra=result)
        except Exception:
            log.exception("mail worker cycle failed")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.MAIL_WORKER_INTERVAL)
        except asyncio.TimeoutError:
            pass
    log.info("mail worker stopped")
