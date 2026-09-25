"""Generated documents. Currently the offer letter.

reportlab's platypus flow layout handles pagination, so a long terms section
does not run off the bottom of the page.
"""

from __future__ import annotations

from datetime import date
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from app.core.config import settings

INK = colors.HexColor("#14212e")
MUTED = colors.HexColor("#5b6b7a")
RULE = colors.HexColor("#d5dce2")
ACCENT = colors.HexColor("#0f766e")


def _styles() -> dict:
    base = getSampleStyleSheet()
    return {
        "company": ParagraphStyle(
            "company", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=15, textColor=INK, leading=18,
        ),
        "meta": ParagraphStyle(
            "meta", parent=base["Normal"], fontSize=8.5, textColor=MUTED, leading=12,
        ),
        "title": ParagraphStyle(
            "title", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=12.5, textColor=INK, leading=16, spaceBefore=6, spaceAfter=8,
        ),
        "h": ParagraphStyle(
            "h", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=9.5, textColor=INK, leading=13, spaceBefore=12, spaceAfter=5,
        ),
        "body": ParagraphStyle(
            "body", parent=base["Normal"], fontSize=9.5, textColor=INK,
            leading=14, alignment=TA_JUSTIFY, spaceAfter=7,
        ),
        "small": ParagraphStyle(
            "small", parent=base["Normal"], fontSize=8.5, textColor=MUTED, leading=12,
        ),
    }


def _money(value) -> str:
    """Indian digit grouping: 12,34,567 rather than 1,234,567."""
    if value is None:
        return "—"
    n = int(round(float(value)))
    sign = "-" if n < 0 else ""
    digits = str(abs(n))
    if len(digits) <= 3:
        grouped = digits
    else:
        head, tail = digits[:-3], digits[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        grouped = ",".join(parts) + "," + tail
    return f"{sign}Rs. {grouped}"


def offer_letter_pdf(
    *,
    candidate_name: str,
    candidate_email: str,
    designation: str,
    department: str | None,
    annual_ctc: float,
    fixed_component: float | None,
    variable_component: float | None,
    joining_bonus: float | None,
    joining_date: date | None,
    valid_till: date | None,
    reference: str,
    issued_by: str,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=22 * mm, rightMargin=22 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Offer of employment — {candidate_name}",
        author=settings.COMPANY_NAME,
        subject=f"Offer letter: {designation}",
    )
    s = _styles()
    story = []

    story.append(Paragraph(settings.COMPANY_NAME, s["company"]))
    story.append(Paragraph(settings.COMPANY_ADDRESS, s["meta"]))
    story.append(Spacer(1, 7))
    story.append(HRFlowable(width="100%", thickness=1.1, color=ACCENT, spaceAfter=12))

    header = Table(
        [[
            Paragraph(f"Reference<br/><b>{reference}</b>", s["small"]),
            Paragraph(
                f"Date<br/><b>{date.today().strftime('%d %B %Y')}</b>", s["small"]
            ),
            Paragraph(
                "Valid until<br/><b>"
                + (valid_till.strftime("%d %B %Y") if valid_till else "Not specified")
                + "</b>",
                s["small"],
            ),
        ]],
        colWidths=[doc.width / 3.0] * 3,
    )
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(header)

    story.append(Paragraph("Offer of employment", s["title"]))
    story.append(Paragraph(f"<b>{candidate_name}</b><br/>{candidate_email}", s["body"]))

    story.append(Paragraph(
        f"We are pleased to offer you the position of <b>{designation}</b>"
        + (f" in the {department} team" if department else "")
        + f" at {settings.COMPANY_NAME}. This letter sets out the principal terms "
        "of that offer.",
        s["body"],
    ))

    story.append(Paragraph("Compensation", s["h"]))
    rows = [["Component", "Amount per annum"]]
    if fixed_component is not None:
        rows.append(["Fixed pay", _money(fixed_component)])
    if variable_component is not None:
        rows.append(["Performance-linked variable", _money(variable_component)])
    if joining_bonus:
        rows.append(["Joining bonus (one time)", _money(joining_bonus)])
    rows.append(["Total cost to company", _money(annual_ctc)])

    table = Table(rows, colWidths=[doc.width * 0.62, doc.width * 0.38])
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, RULE),
        ("LINEABOVE", (0, -1), (-1, -1), 0.9, INK),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)

    if joining_date:
        story.append(Paragraph("Start date", s["h"]))
        story.append(Paragraph(
            f"Your employment is expected to begin on "
            f"<b>{joining_date.strftime('%d %B %Y')}</b>. If that date does not suit "
            "you, tell us and we will try to accommodate a change.",
            s["body"],
        ))

    story.append(Paragraph("Conditions", s["h"]))
    for item in [
        "This offer is subject to verification of your employment history, "
        "education and references, and to your producing evidence of your right "
        "to work.",
        "You confirm that joining us breaches no non-compete, non-solicitation or "
        "confidentiality obligation you owe to any current or former employer.",
        "Your employment is governed by the company handbook and by the policies "
        "in force from time to time, which will be shared on your first day.",
    ]:
        story.append(Paragraph(f"• {item}", s["body"]))

    story.append(Paragraph("Accepting", s["h"]))
    story.append(Paragraph(
        "To accept, reply to this letter"
        + (
            f" on or before {valid_till.strftime('%d %B %Y')}"
            if valid_till else " at your earliest convenience"
        )
        + ". We are glad to talk through any part of it first.",
        s["body"],
    ))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.7, color=RULE, spaceAfter=10))

    sign = Table(
        [[
            Paragraph(
                f"For {settings.COMPANY_NAME}<br/><br/><br/>"
                f"<b>{issued_by}</b><br/>Talent team",
                s["small"],
            ),
            Paragraph(
                "Accepted by<br/><br/><br/>"
                f"<b>{candidate_name}</b><br/>Date: ____________",
                s["small"],
            ),
        ]],
        colWidths=[doc.width / 2.0] * 2,
    )
    sign.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(sign)

    story.append(Spacer(1, 14))
    story.append(Paragraph(
        f"{settings.COMPANY_NAME} · {settings.COMPANY_ADDRESS} · "
        f"{settings.COMPANY_WEBSITE}",
        s["small"],
    ))

    doc.build(story)
    return buffer.getvalue()
