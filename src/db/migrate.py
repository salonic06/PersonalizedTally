from __future__ import annotations

import sqlite3
from datetime import date


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS meta(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  credit_days INTEGER NOT NULL DEFAULT 45,
  gstin TEXT,
  state TEXT,
  state_code TEXT,
  address TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  deleted_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  hsn TEXT,
  unit TEXT,
  default_rate REAL,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  deleted_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Phase 3: raw materials (separate from sellable products in `items`).
CREATE TABLE IF NOT EXISTS raw_materials(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  short_code TEXT NOT NULL UNIQUE,
  unit TEXT NOT NULL DEFAULT 'Kg',
  "type" TEXT,
  reorder_level REAL,
  product_item_id INTEGER REFERENCES items(id),
  is_deleted INTEGER NOT NULL DEFAULT 0,
  deleted_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Each receipt is a lot: internal lot_code = SHORT-DDMMYY-N (N = 1..5 per RM per day).
CREATE TABLE IF NOT EXISTS rm_stock_lots(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  raw_material_id INTEGER NOT NULL REFERENCES raw_materials(id),
  lot_code TEXT NOT NULL UNIQUE,
  received_date TEXT NOT NULL,
  qty_received REAL NOT NULL CHECK(qty_received > 0),
  qty_remaining REAL NOT NULL CHECK(qty_remaining >= 0),
  unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
  supplier_ref TEXT,
  notes TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK(qty_remaining <= qty_received)
);

-- Phase 4–5: production batches, consumption, costing fields.
-- batch_code = B-{DDMMYY}-{batch_no} (full code UNIQUE).
CREATE TABLE IF NOT EXISTS production_batches(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_code TEXT NOT NULL UNIQUE,
  batch_no TEXT NOT NULL,
  product_item_id INTEGER NOT NULL REFERENCES items(id),
  batch_date TEXT NOT NULL,
  notes TEXT,
  batch_yield_kg REAL,
  conversion_cost_per_kg REAL NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  CHECK(batch_yield_kg IS NULL OR batch_yield_kg > 0),
  CHECK(conversion_cost_per_kg >= 0)
);

CREATE TABLE IF NOT EXISTS batch_rm_consumption(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  batch_id INTEGER NOT NULL REFERENCES production_batches(id) ON DELETE RESTRICT,
  rm_stock_lot_id INTEGER NOT NULL REFERENCES rm_stock_lots(id),
  raw_material_id INTEGER NOT NULL REFERENCES raw_materials(id),
  qty_consumed REAL NOT NULL CHECK(qty_consumed > 0),
  source TEXT NOT NULL CHECK(source IN ('fifo','manual')),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS invoices(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  invoice_no TEXT NOT NULL,
  invoice_date TEXT NOT NULL, -- YYYY-MM-DD
  due_date TEXT NOT NULL,     -- YYYY-MM-DD
  total_after_tax REAL NOT NULL, -- from template O43
  notes TEXT,
  excel_path TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  deleted_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(invoice_no)
);

CREATE TABLE IF NOT EXISTS invoice_items(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  line_no INTEGER NOT NULL,
  description TEXT NOT NULL,
  hsn TEXT,
  qty REAL,
  unit TEXT,
  rate REAL,
  amount REAL,
  production_batch_id INTEGER REFERENCES production_batches(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(invoice_id, line_no)
);

CREATE TABLE IF NOT EXISTS payments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  customer_id INTEGER NOT NULL REFERENCES customers(id),
  payment_date TEXT NOT NULL, -- YYYY-MM-DD
  amount REAL NOT NULL CHECK(amount > 0),
  mode TEXT,
  reference TEXT,
  notes TEXT,
  is_deleted INTEGER NOT NULL DEFAULT 0,
  deleted_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Allocation of payments to invoices (supports partial).
CREATE TABLE IF NOT EXISTS allocations(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payment_id INTEGER NOT NULL REFERENCES payments(id) ON DELETE CASCADE,
  invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
  amount REAL NOT NULL CHECK(amount > 0),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(payment_id, invoice_id)
);

-- Append-only trail; application inserts IST wall-clock + optional Windows username.
CREATE TABLE IF NOT EXISTS audit_log(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id INTEGER,
  detail TEXT NOT NULL DEFAULT '',
  operator TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_audit_log_created_at ON audit_log(created_at);

-- Local sign-in (desktop RBAC-lite; not multi-tenant IAM).
CREATE TABLE IF NOT EXISTS app_users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role TEXT NOT NULL CHECK(role IN ('owner','worker')),
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

"""


_VIEWS_SQL = """
DROP VIEW IF EXISTS customer_outstanding;
DROP VIEW IF EXISTS invoice_balances;

-- Paid amount excludes allocations tied to soft-deleted payments.
CREATE VIEW invoice_balances AS
SELECT
  i.id AS invoice_id,
  i.customer_id,
  i.invoice_no,
  i.invoice_date,
  i.due_date,
  i.total_after_tax,
  COALESCE(SUM(CASE WHEN IFNULL(p.is_deleted, 0) = 0 THEN a.amount END), 0) AS paid_amount,
  (i.total_after_tax - COALESCE(SUM(CASE WHEN IFNULL(p.is_deleted, 0) = 0 THEN a.amount END), 0)) AS outstanding
FROM invoices i
LEFT JOIN allocations a ON a.invoice_id = i.id
LEFT JOIN payments p ON p.id = a.payment_id
WHERE i.is_deleted = 0
GROUP BY i.id;

CREATE VIEW customer_outstanding AS
SELECT
  c.id AS customer_id,
  c.name AS customer_name,
  COALESCE(SUM(ib.outstanding), 0) AS outstanding
FROM customers c
LEFT JOIN invoice_balances ib ON ib.customer_id = c.id
WHERE c.is_deleted = 0
GROUP BY c.id;
"""


def _upgrade_schema(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(raw_materials)").fetchall()}
    if not cols:
        return
    if "section" in cols and "type" not in cols:
        conn.execute('ALTER TABLE raw_materials RENAME COLUMN section TO type')
    elif "type" not in cols:
        conn.execute('ALTER TABLE raw_materials ADD COLUMN "type" TEXT')


def _migrate_batch_code_b_ddmmyy_batchno_v1(conn: sqlite3.Connection) -> None:
    """Rewrite batch_code to B-{DDMMYY}-{batch_no}; disambiguate legacy collisions with -{id}."""
    if conn.execute(
        "SELECT 1 FROM meta WHERE key = 'batch_code_b_ddmmyy_batchno_v1' AND value = '1'"
    ).fetchone():
        return
    rows = conn.execute(
        "SELECT id, batch_code, batch_no, batch_date FROM production_batches ORDER BY id"
    ).fetchall()
    seen: set[str] = set()
    for row in rows:
        lid = int(row["id"])
        bn = str(row["batch_no"] or "").strip() or "X"
        bd_s = str(row["batch_date"])
        try:
            rd = date.fromisoformat(bd_s[:10])
        except ValueError:
            continue
        dmy = rd.strftime("%d%m%y")
        new_c = f"B-{dmy}-{bn}"
        if new_c in seen:
            new_c = f"B-{dmy}-{bn}-{lid}"
        seen.add(new_c)
        conn.execute(
            """
            UPDATE production_batches
            SET batch_code = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (new_c, lid),
        )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('batch_code_b_ddmmyy_batchno_v1', '1')"
    )


def _upgrade_production_batches_batch_no(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(production_batches)").fetchall()}
    if not cols:
        return
    if "batch_no" not in cols:
        conn.execute("ALTER TABLE production_batches ADD COLUMN batch_no TEXT")
    rows = conn.execute(
        """
        SELECT id, batch_code FROM production_batches
        WHERE batch_no IS NULL OR TRIM(IFNULL(batch_no, '')) = ''
        """
    ).fetchall()
    for row in rows:
        lid = int(row["id"])
        lc = str(row["batch_code"])
        parts = lc.rsplit("-", 2)
        bn = "B"
        if (
            len(parts) == 3
            and len(parts[1]) == 6
            and parts[1].isdigit()
            and parts[2].isdigit()
        ):
            bn = parts[0]
        elif len(parts) >= 1 and parts[0]:
            bn = parts[0]
        conn.execute(
            """
            UPDATE production_batches
            SET batch_no = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (bn, lid),
        )


def _upgrade_production_batches_phase5(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(production_batches)").fetchall()}
    if not cols:
        return
    if "batch_yield_kg" not in cols:
        conn.execute("ALTER TABLE production_batches ADD COLUMN batch_yield_kg REAL")
    if "conversion_cost_per_kg" not in cols:
        conn.execute(
            "ALTER TABLE production_batches ADD COLUMN conversion_cost_per_kg REAL NOT NULL DEFAULT 0"
        )


def _migrate_conversion_overhead_to_per_kg_v1(conn: sqlite3.Connection) -> None:
    """Legacy fixed conversion_overhead (₹/batch) → conversion_cost_per_kg (₹/kg of output)."""
    if conn.execute(
        "SELECT 1 FROM meta WHERE key = 'conversion_per_kg_migrated_v1' AND value = '1'"
    ).fetchone():
        return
    cols = {r[1] for r in conn.execute("PRAGMA table_info(production_batches)").fetchall()}
    if "conversion_cost_per_kg" not in cols:
        conn.execute(
            "ALTER TABLE production_batches ADD COLUMN conversion_cost_per_kg REAL NOT NULL DEFAULT 0"
        )
    if "conversion_overhead" in cols:
        conn.execute(
            """
            UPDATE production_batches
            SET conversion_cost_per_kg = CASE
              WHEN batch_yield_kg IS NOT NULL AND batch_yield_kg > 1e-12
              THEN conversion_overhead / batch_yield_kg
              ELSE 0
            END
            WHERE conversion_overhead IS NOT NULL AND conversion_overhead > 1e-12
            """
        )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('conversion_per_kg_migrated_v1', '1')"
    )


def _upgrade_invoice_items_production_batch(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(invoice_items)").fetchall()}
    if not cols:
        return
    if "production_batch_id" not in cols:
        conn.execute(
            """
            ALTER TABLE invoice_items
            ADD COLUMN production_batch_id INTEGER REFERENCES production_batches(id) ON DELETE SET NULL
            """
        )


def _migrate_rm_lot_code_format_v1(conn: sqlite3.Connection) -> None:
    """Rename legacy SHORT-YYYYMMDD-SEQ lot codes to SHORT-DDMMYY-N (seq without leading zeros)."""
    if conn.execute(
        "SELECT 1 FROM meta WHERE key = 'rm_lot_code_format_v1' AND value = '1'"
    ).fetchone():
        return
    rows = conn.execute("SELECT id, lot_code, received_date FROM rm_stock_lots").fetchall()
    for row in rows:
        lid = int(row["id"])
        lc = str(row["lot_code"])
        rd_s = str(row["received_date"])
        try:
            rd = date.fromisoformat(rd_s[:10])
        except ValueError:
            continue
        dmy = rd.strftime("%d%m%y")
        parts = lc.rsplit("-", 2)
        if len(parts) != 3:
            continue
        short, mid, seq_s = parts[0], parts[1], parts[2]
        if not seq_s.isdigit():
            continue
        seq = int(seq_s)
        new_lc: str | None = None
        if len(mid) == 8 and mid.isdigit():
            new_lc = f"{short}-{rd.strftime('%d%m%y')}-{seq}"
        elif len(mid) == 6 and mid.isdigit():
            new_lc = f"{short}-{dmy}-{seq}"
        if new_lc is None or new_lc == lc:
            continue
        conn.execute(
            """
            UPDATE rm_stock_lots
            SET lot_code = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (new_lc, lid),
        )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES ('rm_lot_code_format_v1', '1')"
    )


def _upgrade_fg_stock_link_v1(conn: sqlite3.Connection) -> None:
    """Link RM master row to a product for FG stock; tie output lots to production_batches."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(raw_materials)").fetchall()}
    if cols and "product_item_id" not in cols:
        conn.execute("ALTER TABLE raw_materials ADD COLUMN product_item_id INTEGER REFERENCES items(id)")
    lot_cols = {r[1] for r in conn.execute("PRAGMA table_info(rm_stock_lots)").fetchall()}
    if lot_cols and "production_batch_id" not in lot_cols:
        conn.execute(
            """
            ALTER TABLE rm_stock_lots
            ADD COLUMN production_batch_id INTEGER REFERENCES production_batches(id) ON DELETE CASCADE
            """
        )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_rm_lots_one_batch_output
        ON rm_stock_lots(production_batch_id)
        WHERE production_batch_id IS NOT NULL
        """
    )
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS ux_raw_mats_product_fg
        ON raw_materials(product_item_id)
        WHERE product_item_id IS NOT NULL AND is_deleted = 0
        """
    )


def _wipe_all_rm_data_once(conn: sqlite3.Connection) -> None:
    """One-time: clear all raw materials and stock lots (full reset). Bump version to force a fresh wipe."""
    row = conn.execute(
        "SELECT 1 FROM meta WHERE key = 'rm_full_data_wipe_v4' AND value = '1'"
    ).fetchone()
    if row is not None:
        return
    conn.execute("DELETE FROM rm_stock_lots")
    conn.execute("DELETE FROM raw_materials")
    conn.execute(
        """
        INSERT OR REPLACE INTO meta(key, value)
        VALUES ('rm_full_data_wipe_v4', '1')
        """
    )


def _seed_app_users_if_empty(conn: sqlite3.Connection) -> None:
    from ..password_auth import hash_password

    n = conn.execute("SELECT COUNT(*) FROM app_users").fetchone()
    if n is not None and int(n[0]) > 0:
        return
    pairs = (
        ("owner", hash_password("owner123"), "owner"),
        ("worker", hash_password("worker123"), "worker"),
    )
    conn.executemany(
        "INSERT INTO app_users(username, password_hash, role) VALUES (?, ?, ?)",
        pairs,
    )


def _upgrade_audit_log_operator(conn: sqlite3.Connection) -> None:
    cols = {r[1] for r in conn.execute("PRAGMA table_info(audit_log)").fetchall()}
    if not cols:
        return
    if "operator" not in cols:
        conn.execute("ALTER TABLE audit_log ADD COLUMN operator TEXT NOT NULL DEFAULT ''")


def migrate(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)
    _seed_app_users_if_empty(conn)
    _upgrade_schema(conn)
    _upgrade_audit_log_operator(conn)
    _upgrade_production_batches_batch_no(conn)
    _upgrade_production_batches_phase5(conn)
    _migrate_conversion_overhead_to_per_kg_v1(conn)
    _upgrade_invoice_items_production_batch(conn)
    _migrate_batch_code_b_ddmmyy_batchno_v1(conn)
    _wipe_all_rm_data_once(conn)
    _migrate_rm_lot_code_format_v1(conn)
    _upgrade_fg_stock_link_v1(conn)
    conn.executescript(_VIEWS_SQL)

