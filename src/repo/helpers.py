from __future__ import annotations

import re
from datetime import date

# Trailing \b fails when "S." is followed only by spaces — consume optional spaces after S.
_RE_MS = re.compile(r"\bM\s*/\s*S\.?\s*", re.IGNORECASE)
_RE_SHORT = re.compile(r"[^A-Za-z0-9]+")


def parse_iso_date(s: str) -> date:
    return date.fromisoformat(s)


def iso_date(d: date) -> str:
    return d.isoformat()


def normalize_customer_name(name: str) -> str:
    name2 = _RE_MS.sub("", name)
    name2 = re.sub(r"\s+", " ", name2).strip(" -:\t")
    return name2.strip()


def normalize_rm_short_code(s: str) -> str:
    s = _RE_SHORT.sub("", (s or "").strip().upper())
    if len(s) < 1:
        raise ValueError("RM code required (letters/numbers only, no hyphens)")
    if len(s) > 12:
        s = s[:12]
    return s


def suggest_rm_short_code(name: str) -> str:
    alnum = _RE_SHORT.sub("", (name or "").strip().upper())[:12]
    if len(alnum) >= 1:
        return alnum[:12]
    return "RM"


def normalize_batch_no(s: str) -> str:
    t = _RE_SHORT.sub("", (s or "").strip().upper())
    if len(t) < 1:
        raise ValueError("Batch no. required (letters and digits only, no spaces)")
    if len(t) > 20:
        t = t[:20]
    return t


def format_batch_code(batch_no: str, batch_date: date) -> str:
    bn = normalize_batch_no(batch_no)
    dmy = batch_date.strftime("%d%m%y")
    return f"B-{dmy}-{bn}"


def sql_like_pattern(q: str) -> str:
    s = (q or "").strip()
    for a, b in (("\\", "\\\\"), ("%", "\\%"), ("_", "\\_")):
        s = s.replace(a, b)
    return f"%{s}%"
