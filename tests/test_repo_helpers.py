from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.db.conn import connect
from src.db.migrate import migrate
from src.repo import (
    Repo,
    format_batch_code,
    normalize_batch_no,
    normalize_customer_name,
    normalize_rm_short_code,
    suggest_rm_short_code,
)


def test_normalize_customer_name_strips_ms_prefix() -> None:
    assert normalize_customer_name("M/s ABC Corp") == "ABC Corp"
    assert normalize_customer_name("M / S.   Test Co") == "Test Co"


def test_normalize_rm_short_code_strips_non_alnum() -> None:
    assert normalize_rm_short_code("ep-12") == "EP12"


def test_normalize_rm_short_code_empty_raises() -> None:
    with pytest.raises(ValueError, match="RM code required"):
        normalize_rm_short_code("")


def test_suggest_rm_short_code_from_name() -> None:
    assert suggest_rm_short_code("Epoxy Resin") == "EPOXYRESIN"


def test_normalize_batch_no() -> None:
    assert normalize_batch_no("pb-01") == "PB01"


def test_format_batch_code() -> None:
    d = date(2026, 4, 6)
    assert format_batch_code("PB01", d) == "B-060426-PB01"


def test_payments_total_in_date_range(tmp_path: Path) -> None:
    db = tmp_path / "pay.db"
    conn = connect(db)
    migrate(conn)
    repo = Repo(conn)
    cid = repo.upsert_customer("PayCo", 30)
    repo.conn.execute(
        """
        INSERT INTO payments(customer_id, payment_date, amount, mode)
        VALUES (?, ?, ?, ?)
        """,
        (cid, "2026-05-01", 100.0, "UPI"),
    )
    repo.conn.commit()
    assert repo.payments_total_in_date_range(date(2026, 4, 1), date(2026, 5, 31)) == pytest.approx(100.0)
    assert repo.payments_total_in_date_range(date(2026, 6, 1), date(2026, 6, 30)) == 0.0
