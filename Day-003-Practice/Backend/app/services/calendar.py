"""iCalendar invites for interviews.

Written by hand rather than pulled from a library: the format is small, and one
fewer dependency in the deployment is worth more than the convenience. RFC 5545
is strict about line folding and escaping, so both are handled below.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.core.config import settings


def _stamp(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _escape(text: str) -> str:
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold(line: str) -> str:
    """RFC 5545 caps content lines at 75 octets; continuations start with a space."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    chunks, start = [], 0
    while start < len(raw):
        end = min(start + (75 if not chunks else 74), len(raw))
        # Do not split a multi-byte character across the fold.
        while end < len(raw) and (raw[end] & 0xC0) == 0x80:
            end -= 1
        chunk = raw[start:end].decode("utf-8")
        chunks.append(chunk if not chunks else " " + chunk)
        start = end
    return "\r\n".join(chunks)


def interview_invite(
    *,
    uid: str,
    summary: str,
    description: str,
    starts_at: datetime,
    duration_minutes: int,
    location: str | None,
    organizer_email: str,
    attendee_emails: list[str],
    cancelled: bool = False,
    sequence: int = 0,
) -> bytes:
    ends_at = starts_at + timedelta(minutes=duration_minutes)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//{_escape(settings.COMPANY_NAME)}//HRMS Recruit//EN",
        "CALSCALE:GREGORIAN",
        f"METHOD:{'CANCEL' if cancelled else 'REQUEST'}",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_stamp(datetime.now(timezone.utc))}",
        f"DTSTART:{_stamp(starts_at)}",
        f"DTEND:{_stamp(ends_at)}",
        f"SEQUENCE:{sequence}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        f"STATUS:{'CANCELLED' if cancelled else 'CONFIRMED'}",
        "TRANSP:OPAQUE",
        f"ORGANIZER;CN={_escape(settings.MAIL_FROM_NAME)}:mailto:{organizer_email}",
    ]
    if location:
        lines.append(f"LOCATION:{_escape(location)}")
    for email in attendee_emails:
        lines.append(
            "ATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:"
            f"mailto:{email}"
        )
    if not cancelled:
        lines += [
            "BEGIN:VALARM",
            "TRIGGER:-PT30M",
            "ACTION:DISPLAY",
            "DESCRIPTION:Interview in 30 minutes",
            "END:VALARM",
        ]
    lines += ["END:VEVENT", "END:VCALENDAR"]

    return ("\r\n".join(_fold(line) for line in lines) + "\r\n").encode("utf-8")
