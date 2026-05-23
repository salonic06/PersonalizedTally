from __future__ import annotations

from datetime import date
from pathlib import Path

from src.db.conn import connect
from src.db.migrate import migrate
from src.notifications import collect_notifications
from src.repo import Repo


def test_collect_notifications_reorder_and_due(tmp_path: Path) -> None:
    conn = connect(tmp_path / "notify.db")
    migrate(conn)
    repo = Repo(conn)

    rm_id = repo.add_raw_material("Epoxy", "EPX", reorder_level=100.0)
    repo.receive_rm_stock_lot(rm_id, date(2026, 5, 1), 50.0, 10.0)

    cid = repo.upsert_customer("Due Co", 30)
    inv_id = repo.create_invoice(cid, "D-1", date(2026, 5, 1), 1000.0, None)
    repo.conn.execute(
        "UPDATE invoices SET due_date = ? WHERE id = ?",
        ("2026-05-22", inv_id),
    )
    repo.conn.commit()

    today = date(2026, 5, 22)
    due_rows = repo.due_rows(today, only_due_today=True, due_from=None, due_to=None)
    assert len(due_rows) >= 1

    alerts = collect_notifications(repo, today)
    kinds = {a.kind for a in alerts}
    assert "reorder_low" in kinds
    assert "due_today" in kinds
    due_alert = next(a for a in alerts if a.kind == "due_today")
    assert "Due today" in due_alert.title
    assert "D-1" in due_alert.detail
    assert "late" not in due_alert.detail.lower()

    overdue_inv = repo.create_invoice(cid, "O-1", date(2026, 4, 1), 500.0, None)
    repo.conn.execute(
        "UPDATE invoices SET due_date = ? WHERE id = ?",
        ("2026-05-01", overdue_inv),
    )
    repo.conn.commit()

    alerts2 = collect_notifications(repo, date(2026, 5, 22))
    assert "overdue" in {a.kind for a in alerts2}
    od = next(a for a in alerts2 if a.kind == "overdue")
    assert " days" in od.detail
    assert "same rows" not in od.detail.lower()
