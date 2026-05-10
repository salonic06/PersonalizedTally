from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path


def backups_dir_for_db(db_path: Path) -> Path:
    """`<repo>/data/backups` when `db_path` is `<repo>/data/personalized_tally.db`."""
    return db_path.parent / "backups"


def backup_sqlite_database(
    conn: sqlite3.Connection,
    *,
    dest_dir: Path | None = None,
    filename_stem: str = "personalized_tally",
) -> Path:
    """
    Hot-copy the open database using SQLite's backup API (safe with WAL).
    Returns path to the new `.db` file.
    """
    rows = conn.execute("PRAGMA database_list").fetchall()
    main_file = next((str(r[2]) for r in rows if r[1] == "main"), "")
    if not main_file:
        raise RuntimeError("Cannot resolve main database path (empty or in-memory?).")
    main = Path(main_file)
    if dest_dir is None:
        dest_dir = backups_dir_for_db(main)
    dest_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = dest_dir / f"{filename_stem}_backup_{ts}.db"
    if dest.exists():
        dest.unlink()

    bck = sqlite3.connect(str(dest))
    try:
        conn.backup(bck)
        bck.commit()
    finally:
        bck.close()
    return dest.resolve()
