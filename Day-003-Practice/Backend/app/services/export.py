"""CSV exports.

Written with the csv module rather than string joins so a candidate named
O'Brien, or a note containing a comma or newline, cannot corrupt the file.
Excel is the usual destination, hence the BOM: without it Excel decodes UTF-8
as latin-1 and non-ASCII names come out as mojibake.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, (list, tuple)):
        return "; ".join(str(v) for v in value)
    text = str(value)
    # A cell starting with one of these is treated as a formula by spreadsheet
    # apps. Prefixing a quote neutralises it.
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        text = "'" + text
    return text


def to_csv(headers: list[str], rows: list[list]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_cell(v) for v in row])
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")


def filename(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M')}.csv"
