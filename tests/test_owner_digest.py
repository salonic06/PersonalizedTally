from __future__ import annotations

from datetime import date
from pathlib import Path

from src.db.conn import connect
from src.db.migrate import migrate
from src.notifications import AppNotification, collect_notifications
from src.owner_digest import build_owner_digest, format_owner_digest
from src.repo import Repo


def test_format_owner_digest_empty() -> None:
    text = format_owner_digest([], today=date(2026, 5, 22))
    assert "All clear" in text
    assert "22 May 2026" in text


def test_build_owner_digest_from_db(tmp_path: Path) -> None:
    conn = connect(tmp_path / "digest.db")
    migrate(conn)
    repo = Repo(conn)
    rm_id = repo.add_raw_material("Glue", "GLU", reorder_level=50.0)
    repo.receive_rm_stock_lot(rm_id, date(2026, 5, 1), 10.0, 1.0)
    body = build_owner_digest(repo, date(2026, 5, 22))
    assert "Low stock" in body
    assert "GLU" in body

    notes = collect_notifications(repo, date(2026, 5, 22))
    assert format_owner_digest(notes, today=date(2026, 5, 22)) == body
