from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    # Autocommit unless `transaction()` opens BEGIN — avoids nested-transaction errors
    # when repo helpers call `transaction(conn)` after other statements.
    conn.isolation_level = None
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection):
    try:
        # Prefer the DB-API transaction semantics to avoid conflicts with
        # APIs like executescript() that may implicitly manage transactions.
        conn.execute("BEGIN;")
        yield
        conn.commit()
    except Exception:
        conn.rollback()
        raise

