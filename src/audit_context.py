"""Audit log timestamp (IST) and desktop operator label."""

from __future__ import annotations

import getpass
from datetime import datetime, timedelta, timezone

# Fixed UTC+5:30 — matches India Standard Time year-round (no DST).
# Avoids ``zoneinfo`` + optional ``tzdata`` wheel on minimal Windows/conda venvs.
IST = timezone(timedelta(hours=5, minutes=30))

_operator_override: str | None = None


def set_audit_operator_override(name: str | None) -> None:
    """Use signed-in app username for audit rows instead of OS login."""
    global _operator_override
    t = (name or "").strip()[:120]
    _operator_override = t or None


def now_ist_wall_clock() -> str:
    """SQLite TEXT timestamp for audit rows — India Standard Time (no TZ suffix)."""
    return datetime.now(IST).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def audit_operator_name() -> str:
    if _operator_override:
        return _operator_override
    try:
        return (getpass.getuser() or "").strip()[:120]
    except Exception:
        return ""
