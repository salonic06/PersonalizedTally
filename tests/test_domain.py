from __future__ import annotations

from datetime import date, timedelta

from src.domain import compute_due_date


def test_compute_due_date_adds_credit_days() -> None:
    inv = date(2026, 4, 1)
    assert compute_due_date(inv, 45) == inv + timedelta(days=45)


def test_compute_due_date_zero_credit() -> None:
    inv = date(2026, 5, 10)
    assert compute_due_date(inv, 0) == inv
