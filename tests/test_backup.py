from __future__ import annotations

import sqlite3
from pathlib import Path

from src.backup import backup_sqlite_database, backups_dir_for_db


def test_backups_dir_for_db() -> None:
    db = Path("/tmp/proj/data/app.db")
    assert backups_dir_for_db(db) == Path("/tmp/proj/data/backups")


def test_backup_sqlite_database_copies_data(tmp_path: Path) -> None:
    src = tmp_path / "source.db"
    conn = sqlite3.connect(str(src))
    conn.execute("CREATE TABLE t(x INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()

    dest_dir = tmp_path / "backups"
    out = backup_sqlite_database(conn, dest_dir=dest_dir, filename_stem="trial")
    conn.close()

    assert out.parent.resolve() == dest_dir.resolve()
    assert out.name.startswith("trial_backup_")
    assert out.suffix == ".db"

    c2 = sqlite3.connect(str(out))
    n = c2.execute("SELECT x FROM t").fetchone()[0]
    c2.close()
    assert int(n) == 42
