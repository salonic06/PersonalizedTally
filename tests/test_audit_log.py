from __future__ import annotations

from datetime import date
from pathlib import Path

import sqlite3

from src.db.migrate import migrate
from src.repo import Repo


def test_audit_log_records_invoice_and_trash(tmp_path: Path) -> None:
    db_path = tmp_path / "audit.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    migrate(conn)
    repo = Repo(conn)
    cid = repo.upsert_customer("Acme Corp", 30)
    inv_id = repo.create_invoice(cid, "001", date(2026, 4, 1), 1180.0, None)
    rows = repo.list_audit_log(limit=20)
    created = [r for r in rows if r.action == "invoice_created" and r.entity_id == inv_id]
    assert len(created) == 1
    assert "Acme Corp" in created[0].detail
    assert "001" in created[0].detail

    repo.soft_delete_invoice(inv_id)
    rows2 = repo.list_audit_log(limit=5)
    assert rows2[0].action == "invoice_trashed"
    assert rows2[0].entity_id == inv_id

    repo.restore_invoice(inv_id)
    rows3 = repo.list_audit_log(limit=3)
    assert rows3[0].action == "invoice_restored"

    conn.close()
