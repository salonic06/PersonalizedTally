from __future__ import annotations

from pathlib import Path

from src.db.conn import connect
from src.db.migrate import migrate
from src.repo import Repo


def test_verify_login_default_accounts(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    conn = connect(db)
    migrate(conn)
    repo = Repo(conn)
    assert repo.verify_login("owner", "owner123") == "owner"
    assert repo.verify_login("OWNER", "owner123") == "owner"
    assert repo.verify_login("worker", "worker123") == "worker"
    assert repo.verify_login("owner", "nope") is None
    assert repo.verify_login("nobody", "owner123") is None


def test_update_own_password(tmp_path: Path) -> None:
    db = tmp_path / "t.db"
    conn = connect(db)
    migrate(conn)
    repo = Repo(conn)
    repo.update_own_password("worker", "worker123", "newpass999")
    assert repo.verify_login("worker", "newpass999") == "worker"
    assert repo.verify_login("worker", "worker123") is None
