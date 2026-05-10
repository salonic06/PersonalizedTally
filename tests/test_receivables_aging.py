from __future__ import annotations

from datetime import date, timedelta

from src.domain import receivable_aging_bucket


def test_aging_bucket_current_and_due_today() -> None:
    today = date(2026, 6, 15)
    assert receivable_aging_bucket(date(2026, 7, 1), today) == "current"
    assert receivable_aging_bucket(today, today) == "current"


def test_aging_bucket_past_due_brackets() -> None:
    today = date(2026, 6, 15)
    assert receivable_aging_bucket(today - timedelta(days=1), today) == "p1_30"
    assert receivable_aging_bucket(today - timedelta(days=30), today) == "p1_30"
    assert receivable_aging_bucket(today - timedelta(days=31), today) == "p31_60"
    assert receivable_aging_bucket(today - timedelta(days=60), today) == "p31_60"
    assert receivable_aging_bucket(today - timedelta(days=61), today) == "p61_90"
    assert receivable_aging_bucket(today - timedelta(days=90), today) == "p61_90"
    assert receivable_aging_bucket(today - timedelta(days=91), today) == "p90_plus"
