from __future__ import annotations

from datetime import date
from pathlib import Path

from src.db.conn import connect
from src.db.migrate import migrate
from src.notifications import collect_notifications
from src.repo import Repo


def test_overdue_alert_count_matches_due_page_without_date_range(tmp_path: Path) -> None:
    conn = connect(tmp_path / "overdue_match.db")
    migrate(conn)
    repo = Repo(conn)
    cid = repo.upsert_customer("Late Payer", 30)
    today = date(2026, 5, 22)

    ids = []
    for i, due in enumerate(
        ("2026-01-15", "2026-02-10", "2026-03-01", "2026-04-05"), start=1
    ):
        inv = repo.create_invoice(cid, f"OLD-{i}", date(2026, 1, 1), 1000.0 * i, None)
        repo.conn.execute(
            "UPDATE invoices SET due_date = ? WHERE id = ?",
            (due, inv),
        )
        ids.append(inv)
    repo.conn.commit()

    overdue_rows = repo.due_rows(today, only_overdue=True, due_from=None, due_to=None)
    assert len(overdue_rows) == 4

    # Narrow month window (like old Due page default) would hide older dues.
    narrow = repo.due_rows(
        today,
        only_overdue=True,
        due_from=date(2026, 5, 1),
        due_to=date(2026, 6, 30),
    )
    assert len(narrow) < 4

    alerts = collect_notifications(repo, today)
    overdue_alert = next(a for a in alerts if a.kind == "overdue")
    assert "4 invoice" in overdue_alert.title


def test_trashed_payment_not_counted_in_invoice_balance(tmp_path: Path) -> None:
    conn = connect(tmp_path / "trash_pay.db")
    migrate(conn)
    repo = Repo(conn)
    cid = repo.upsert_customer("PayTrash Co", 30)
    inv_id = repo.create_invoice(cid, "PT-1", date(2026, 5, 1), 1000.0, None)
    pay_id = repo.create_payment(cid, date(2026, 5, 10), 400.0)
    row = repo.conn.execute(
        "SELECT outstanding FROM invoice_balances WHERE invoice_id = ?",
        (inv_id,),
    ).fetchone()
    assert float(row["outstanding"]) == 600.0

    repo.soft_delete_payment(pay_id)
    row2 = repo.conn.execute(
        "SELECT outstanding FROM invoice_balances WHERE invoice_id = ?",
        (inv_id,),
    ).fetchone()
    assert float(row2["outstanding"]) == 1000.0
