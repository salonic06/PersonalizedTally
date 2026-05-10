from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from .db.conn import transaction
from .audit_context import audit_operator_name, now_ist_wall_clock
from .password_auth import verify_password
from .domain import compute_due_date, receivable_aging_bucket


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _iso(d: date) -> str:
    return d.isoformat()


# Trailing \b fails when "S." is followed only by spaces — consume optional spaces after S.
_RE_MS = re.compile(r"\bM\s*/\s*S\.?\s*", re.IGNORECASE)
_RE_SHORT = re.compile(r"[^A-Za-z0-9]+")


def normalize_customer_name(name: str) -> str:
    # Remove common "M/s" business prefix wherever it appears.
    name2 = _RE_MS.sub("", name)
    name2 = re.sub(r"\s+", " ", name2).strip(" -:\t")
    return name2.strip()


def normalize_rm_short_code(s: str) -> str:
    s = _RE_SHORT.sub("", (s or "").strip().upper())
    if len(s) < 1:
        raise ValueError("RM code required (letters/numbers only, no hyphens)")
    if len(s) > 12:
        s = s[:12]
    return s


def suggest_rm_short_code(name: str) -> str:
    alnum = _RE_SHORT.sub("", (name or "").strip().upper())[:12]
    if len(alnum) >= 1:
        return alnum[:12]
    return "RM"


def normalize_batch_no(s: str) -> str:
    """Production batch number segment (alphanumeric, no hyphens); used in batch_code B-DDMMYY-BATCHNO."""
    t = _RE_SHORT.sub("", (s or "").strip().upper())
    if len(t) < 1:
        raise ValueError("Batch no. required (letters and digits only, no spaces)")
    if len(t) > 20:
        t = t[:20]
    return t


def format_batch_code(batch_no: str, batch_date: date) -> str:
    """Full internal batch code: B-{DDMMYY}-{batch_no} (batch_no normalized)."""
    bn = normalize_batch_no(batch_no)
    dmy = batch_date.strftime("%d%m%y")
    return f"B-{dmy}-{bn}"


@dataclass(frozen=True)
class DueRow:
    customer_id: int
    customer_name: str
    invoice_id: int
    invoice_no: str
    invoice_date: date
    due_date: date
    outstanding: float
    days_overdue: int
    excel_path: str | None = None


@dataclass(frozen=True)
class CustomerDueRow:
    customer_id: int
    customer_name: str
    outstanding: float
    oldest_due_date: date
    invoice_count: int
    days_overdue: int


def _sql_like_pattern(q: str) -> str:
    s = (q or "").strip()
    for a, b in (("\\", "\\\\"), ("%", "\\%"), ("_", "\\_")):
        s = s.replace(a, b)
    return f"%{s}%"


@dataclass(frozen=True)
class ReceivablesAgingTotals:
    """Portfolio outstanding split by days past invoice due date."""

    current: float
    past_1_30: float
    past_31_60: float
    past_61_90: float
    past_90_plus: float

    def grand_total(self) -> float:
        return (
            self.current
            + self.past_1_30
            + self.past_31_60
            + self.past_61_90
            + self.past_90_plus
        )


@dataclass(frozen=True)
class CustomerAgingRow:
    customer_id: int
    customer_name: str
    current: float
    past_1_30: float
    past_31_60: float
    past_61_90: float
    past_90_plus: float

    def row_total(self) -> float:
        return (
            self.current
            + self.past_1_30
            + self.past_31_60
            + self.past_61_90
            + self.past_90_plus
        )


@dataclass(frozen=True)
class AuditLogRow:
    id: int
    created_at: str
    action: str
    entity_type: str
    entity_id: int | None
    detail: str
    operator: str


@dataclass(frozen=True)
class DashboardSummary:
    customer_count: int
    item_count: int
    raw_material_count: int
    production_batch_count: int
    invoice_count: int
    payment_count: int
    total_outstanding: float
    due_today_invoice_count: int
    overdue_invoice_count: int
    # Calendar MTD / YTD (uses `today` passed to dashboard_summary).
    mtd_sales_ex_gst: float
    ytd_sales_ex_gst: float
    mtd_collections: float
    ytd_collections: float
    mtd_invoice_count: int
    ytd_invoice_count: int
    mtd_cogs: float
    ytd_cogs: float
    mtd_gross_profit: float
    ytd_gross_profit: float


@dataclass(frozen=True)
class InvoiceGrossProfit:
    """Per-invoice margin on pre-GST revenue vs batch COGS (Phase 6)."""

    invoice_id: int
    invoice_no: str
    invoice_date: date
    customer_name: str
    revenue_ex_gst: float
    total_after_tax: float
    cogs: float
    gross_profit: float
    line_count: int
    lines_with_cogs: int
    cogs_complete: bool


@dataclass(frozen=True)
class AnalyticsMonthRow:
    year_month: str  # YYYY-MM
    sales_ex_gst: float
    bill_total_after_tax: float
    est_output_gst: float
    payments_received: float
    cogs: float
    gross_profit: float


@dataclass(frozen=True)
class AnalyticsYearRow:
    year: str  # YYYY
    sales_ex_gst: float
    bill_total_after_tax: float
    est_output_gst: float
    payments_received: float
    cogs: float
    gross_profit: float


@dataclass(frozen=True)
class SearchHit:
    kind: str  # customer | invoice | payment | item | raw_material | rm_lot
    record_id: int
    title: str
    detail: str
    customer_id: int | None = None
    invoice_id: int | None = None
    excel_path: str | None = None
    raw_material_id: int | None = None


class Repo:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def verify_login(self, username: str, password: str) -> str | None:
        """Return ``owner`` or ``worker`` if credentials match; otherwise ``None``."""
        u = (username or "").strip()
        if not u:
            return None
        row = self.conn.execute(
            "SELECT password_hash, role FROM app_users WHERE lower(username) = lower(?)",
            (u,),
        ).fetchone()
        if row is None:
            return None
        if verify_password(password, str(row["password_hash"])):
            return str(row["role"])
        return None

    def update_own_password(self, username: str, old_password: str, new_password: str) -> None:
        """Replace password for ``username`` after verifying ``old_password``."""
        from .password_auth import hash_password

        u = (username or "").strip()
        if not u:
            raise ValueError("Username required")
        nw = new_password or ""
        if len(nw) < 6:
            raise ValueError("New password must be at least 6 characters.")
        if nw != nw.strip():
            raise ValueError("Password cannot start or end with spaces.")
        if self.verify_login(u, old_password) is None:
            raise ValueError("Current password is incorrect.")
        self.conn.execute(
            """
            UPDATE app_users
            SET password_hash = ?
            WHERE lower(username) = lower(?)
            """,
            (hash_password(nw), u),
        )

    # ---- customers ----
    def list_customers(self) -> list[sqlite3.Row]:
        cur = self.conn.execute(
            "SELECT id, name, credit_days FROM customers WHERE is_deleted = 0 ORDER BY name"
        )
        return list(cur.fetchall())

    def get_customer(self, customer_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT id, name, credit_days, gstin, state, state_code, address
            FROM customers
            WHERE id = ? AND is_deleted = 0
            """,
            (customer_id,),
        ).fetchone()

    def upsert_customer(self, name: str, credit_days: int = 45) -> int:
        name = normalize_customer_name(name.strip())
        if not name:
            raise ValueError("Customer name required")
        credit_days = int(credit_days)
        if credit_days <= 0 or credit_days > 3650:
            raise ValueError("Credit days must be between 1 and 3650")

        self.conn.execute(
            """
            INSERT INTO customers(name, credit_days)
            VALUES (?, ?)
            ON CONFLICT(name) DO UPDATE SET
              credit_days = excluded.credit_days,
              updated_at = datetime('now')
            """,
            (name, credit_days),
        )
        row = self.conn.execute("SELECT id FROM customers WHERE name = ?", (name,)).fetchone()
        assert row is not None
        return int(row["id"])

    def update_customer_details(
        self,
        customer_id: int,
        *,
        name: str,
        credit_days: int,
        gstin: str = "",
        state: str = "",
        state_code: str = "",
        address: str = "",
    ) -> None:
        name = normalize_customer_name(name.strip())
        if not name:
            raise ValueError("Customer name required")
        credit_days = int(credit_days)
        if credit_days <= 0 or credit_days > 3650:
            raise ValueError("Credit days must be between 1 and 3650")

        self.conn.execute(
            """
            UPDATE customers
            SET name = ?,
                credit_days = ?,
                gstin = ?,
                state = ?,
                state_code = ?,
                address = ?,
                updated_at = datetime('now')
            WHERE id = ? AND is_deleted = 0
            """,
            (
                name,
                credit_days,
                gstin.strip() or None,
                state.strip() or None,
                state_code.strip() or None,
                address.strip() or None,
                customer_id,
            ),
        )

    # ---- items master ----
    def list_items(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT id, name, hsn, unit, default_rate FROM items WHERE is_deleted = 0 ORDER BY name"
            ).fetchall()
        )

    def get_item(self, item_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT id, name, hsn, unit, default_rate
            FROM items WHERE id = ? AND is_deleted = 0
            """,
            (int(item_id),),
        ).fetchone()

    def upsert_item(self, name: str, hsn: str = "", unit: str = "", default_rate: float | None = None) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Product name required")
        rate = None if default_rate is None else float(default_rate)
        self.conn.execute(
            """
            INSERT INTO items(name, hsn, unit, default_rate)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
              hsn = excluded.hsn,
              unit = excluded.unit,
              default_rate = excluded.default_rate,
              updated_at = datetime('now')
            """,
            (name, (hsn or "").strip() or None, (unit or "").strip() or None, rate),
        )
        row = self.conn.execute("SELECT id FROM items WHERE name = ?", (name,)).fetchone()
        assert row is not None
        return int(row["id"])

    # ---- raw materials & stock lots (Phase 3) ----
    def list_raw_materials(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT id, name, short_code, unit, "type" AS rm_type, reorder_level, product_item_id
                FROM raw_materials
                WHERE is_deleted = 0
                ORDER BY short_code
                """
            ).fetchall()
        )

    def get_raw_material(self, raw_material_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT id, name, short_code, unit, "type" AS rm_type, reorder_level, product_item_id
            FROM raw_materials
            WHERE id = ? AND is_deleted = 0
            """,
            (raw_material_id,),
        ).fetchone()

    def resolve_item_id_from_description(self, description: str) -> int | None:
        """Match invoice line description to active product name (exact, trimmed)."""
        d = (description or "").strip()
        if not d:
            return None
        row = self.conn.execute(
            "SELECT id FROM items WHERE name = ? AND is_deleted = 0",
            (d,),
        ).fetchone()
        return int(row["id"]) if row is not None else None

    def reduce_raw_material_stock_fifo(self, raw_material_id: int, qty: float) -> None:
        """Reduce qty across lots oldest-first (same order as batch RM consumption). All lots for this RM.

        Caller must wrap in ``transaction(conn)`` if multiple steps need atomicity.
        """
        q = float(qty)
        if q <= 1e-12:
            return
        need = q
        lots = self.conn.execute(
            """
            SELECT l.id, l.qty_remaining
            FROM rm_stock_lots l
            JOIN raw_materials r ON r.id = l.raw_material_id AND r.is_deleted = 0
            WHERE l.raw_material_id = ? AND l.qty_remaining > 1e-9
            ORDER BY l.received_date ASC, l.created_at ASC, l.id ASC
            """,
            (int(raw_material_id),),
        ).fetchall()
        for lot_row in lots:
            if need <= 1e-12:
                break
            lid = int(lot_row["id"])
            rem = float(lot_row["qty_remaining"])
            take = min(rem, need)
            self._reduce_lot_qty(lid, take)
            need -= take
        if need > 1e-9:
            raise ValueError(
                f"Not enough finished-goods stock (FIFO): need {q:,.3f} kg, "
                f"short by {need:,.3f} kg."
            )

    def raw_material_id_for_finished_product(self, product_item_id: int) -> int | None:
        """RM master row linked to this product for finished-goods stock (e.g. LP750 → Lampol 750)."""
        row = self.conn.execute(
            """
            SELECT id FROM raw_materials
            WHERE product_item_id = ? AND is_deleted = 0
            LIMIT 1
            """,
            (int(product_item_id),),
        ).fetchone()
        return int(row["id"]) if row is not None else None

    def _assert_unique_product_item_link(
        self, product_item_id: int | None, *, exclude_raw_material_id: int | None = None
    ) -> None:
        if product_item_id is None:
            return
        q = """
            SELECT id FROM raw_materials
            WHERE product_item_id = ? AND is_deleted = 0
            """
        params: list = [int(product_item_id)]
        if exclude_raw_material_id is not None:
            q += " AND id != ?"
            params.append(int(exclude_raw_material_id))
        if self.conn.execute(q, params).fetchone() is not None:
            raise ValueError(
                "Another raw material is already linked to that product for finished-goods stock."
            )

    def add_raw_material(
        self,
        name: str,
        short_code: str,
        unit: str = "Kg",
        material_type: str | None = None,
        reorder_level: float | None = None,
        *,
        product_item_id: int | None = None,
    ) -> int:
        name = (name or "").strip()
        if not name:
            raise ValueError("Name required")
        sc = normalize_rm_short_code(short_code)
        u = (unit or "").strip() or "Kg"
        mt = (material_type or "").strip() or None
        rl = None if reorder_level is None else float(reorder_level)
        self._assert_unique_product_item_link(product_item_id, exclude_raw_material_id=None)
        if product_item_id is not None:
            ok = self.conn.execute(
                "SELECT 1 FROM items WHERE id = ? AND is_deleted = 0", (int(product_item_id),)
            ).fetchone()
            if ok is None:
                raise ValueError("Product not found for finished-goods link")
        cur = self.conn.execute(
            """
            INSERT INTO raw_materials(name, short_code, unit, "type", reorder_level, product_item_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, sc, u, mt, rl, product_item_id),
        )
        return int(cur.lastrowid)

    def update_raw_material(
        self,
        raw_material_id: int,
        *,
        name: str,
        short_code: str,
        unit: str = "Kg",
        material_type: str | None = None,
        reorder_level: float | None = None,
        product_item_id: int | None = None,
    ) -> None:
        name = (name or "").strip()
        if not name:
            raise ValueError("Name required")
        sc = normalize_rm_short_code(short_code)
        u = (unit or "").strip() or "Kg"
        mt = (material_type or "").strip() or None
        rl = None if reorder_level is None else float(reorder_level)
        self._assert_unique_product_item_link(
            product_item_id, exclude_raw_material_id=int(raw_material_id)
        )
        if product_item_id is not None:
            ok = self.conn.execute(
                "SELECT 1 FROM items WHERE id = ? AND is_deleted = 0", (int(product_item_id),)
            ).fetchone()
            if ok is None:
                raise ValueError("Product not found for finished-goods link")
        cur = self.conn.execute(
            """
            UPDATE raw_materials
            SET name = ?, short_code = ?, unit = ?, "type" = ?, reorder_level = ?,
                product_item_id = ?, updated_at = datetime('now')
            WHERE id = ? AND is_deleted = 0
            """,
            (name, sc, u, mt, rl, product_item_id, raw_material_id),
        )
        if cur.rowcount == 0:
            raise ValueError("Raw material not found")

    def raw_material_on_hand(self, raw_material_id: int) -> float:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(qty_remaining), 0) AS q
            FROM rm_stock_lots
            WHERE raw_material_id = ?
            """,
            (raw_material_id,),
        ).fetchone()
        return float(row["q"]) if row else 0.0

    def list_raw_material_balances(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT
                  r.id AS raw_material_id,
                  r.name AS name,
                  r.short_code AS short_code,
                  r.unit AS unit,
                  r."type" AS rm_type,
                  r.reorder_level AS reorder_level,
                  COALESCE(SUM(l.qty_remaining), 0) AS on_hand
                FROM raw_materials r
                LEFT JOIN rm_stock_lots l ON l.raw_material_id = r.id
                WHERE r.is_deleted = 0
                GROUP BY r.id
                ORDER BY IFNULL(r."type", ''), r.short_code
                """
            ).fetchall()
        )

    def list_distinct_rm_types(self) -> list[str]:
        """Distinct non-empty types from active raw materials (for Setup type dropdown)."""
        rows = self.conn.execute(
            """
            SELECT DISTINCT TRIM("type") AS t
            FROM raw_materials
            WHERE is_deleted = 0 AND "type" IS NOT NULL AND TRIM("type") != ''
            ORDER BY t COLLATE NOCASE
            """
        ).fetchall()
        return [str(r["t"]) for r in rows]

    def peek_next_lot_code(self, raw_material_id: int, received_date: date) -> str:
        row = self.conn.execute(
            "SELECT short_code FROM raw_materials WHERE id = ? AND is_deleted = 0",
            (raw_material_id,),
        ).fetchone()
        if row is None:
            raise ValueError("Raw material not found")
        short = str(row["short_code"])
        dmy = received_date.strftime("%d%m%y")
        prefix = f"{short}-{dmy}-"
        rows = self.conn.execute(
            """
            SELECT lot_code FROM rm_stock_lots
            WHERE raw_material_id = ? AND received_date = ?
            """,
            (raw_material_id, _iso(received_date)),
        ).fetchall()
        max_n = 0
        for r in rows:
            lc = str(r["lot_code"])
            if not lc.startswith(prefix):
                continue
            tail = lc[len(prefix) :]
            if tail.isdigit():
                max_n = max(max_n, int(tail))
        return f"{prefix}{max_n + 1}"

    def receive_rm_stock_lot(
        self,
        raw_material_id: int,
        received_date: date,
        qty: float,
        unit_cost: float,
        supplier_ref: str = "",
        notes: str = "",
    ) -> tuple[int, str]:
        q = float(qty)
        if q <= 0:
            raise ValueError("Quantity must be > 0")
        uc = float(unit_cost)
        if uc < 0:
            raise ValueError("Unit cost cannot be negative")
        cnt = self.conn.execute(
            """
            SELECT COUNT(*) AS c FROM rm_stock_lots
            WHERE raw_material_id = ? AND received_date = ?
            """,
            (raw_material_id, _iso(received_date)),
        ).fetchone()
        if int(cnt["c"] if cnt else 0) >= 5:
            raise ValueError("At most 5 lots per raw material per calendar day.")
        lot_code = self.peek_next_lot_code(raw_material_id, received_date)
        cur = self.conn.execute(
            """
            INSERT INTO rm_stock_lots(
              raw_material_id, lot_code, received_date,
              qty_received, qty_remaining, unit_cost, supplier_ref, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                raw_material_id,
                lot_code,
                _iso(received_date),
                q,
                q,
                uc,
                (supplier_ref or "").strip() or None,
                (notes or "").strip() or None,
            ),
        )
        lid = int(cur.lastrowid)
        self.audit_log_append(
            action="rm_lot_received",
            entity_type="rm_lot",
            entity_id=lid,
            detail=(
                f"lot_code={lot_code}; qty={q:.3f}; unit_cost={uc:.2f}; "
                f"rm_id={raw_material_id}; received={_iso(received_date)}"
            ),
        )
        return lid, lot_code

    def list_rm_stock_lots(self, raw_material_id: int | None = None) -> list[sqlite3.Row]:
        if raw_material_id is None:
            return list(
                self.conn.execute(
                    """
                    SELECT
                      l.id,
                      l.lot_code,
                      l.received_date,
                      l.qty_received,
                      l.qty_remaining,
                      l.unit_cost,
                      l.supplier_ref,
                      l.notes,
                      l.production_batch_id,
                      r.short_code AS rm_code,
                      r.unit AS unit,
                      r.id AS raw_material_id
                    FROM rm_stock_lots l
                    JOIN raw_materials r ON r.id = l.raw_material_id AND r.is_deleted = 0
                    ORDER BY l.received_date DESC, l.created_at DESC, l.id DESC
                    """
                ).fetchall()
            )
        return list(
            self.conn.execute(
                """
                SELECT
                  l.id,
                  l.lot_code,
                  l.received_date,
                  l.qty_received,
                  l.qty_remaining,
                  l.unit_cost,
                  l.supplier_ref,
                  l.notes,
                  l.production_batch_id,
                  r.short_code AS rm_code,
                  r.unit AS unit,
                  r.id AS raw_material_id
                FROM rm_stock_lots l
                JOIN raw_materials r ON r.id = l.raw_material_id AND r.is_deleted = 0
                WHERE l.raw_material_id = ?
                ORDER BY l.received_date DESC, l.created_at DESC, l.id DESC
                """,
                (raw_material_id,),
            ).fetchall()
        )

    def set_raw_material_on_hand(
        self,
        raw_material_id: int,
        target_qty: float,
        *,
        notes: str = "On-hand adjustment",
    ) -> None:
        ok = self.conn.execute(
            "SELECT 1 FROM raw_materials WHERE id = ? AND is_deleted = 0", (raw_material_id,)
        ).fetchone()
        if ok is None:
            raise ValueError("Raw material not found")
        target = float(target_qty)
        if target < 0:
            raise ValueError("On-hand cannot be negative")
        current = self.raw_material_on_hand(raw_material_id)
        delta = target - current
        if abs(delta) < 1e-12:
            return
        if delta > 0:
            self.receive_rm_stock_lot(
                raw_material_id,
                date.today(),
                delta,
                0.0,
                notes=notes,
            )
            return
        need = -delta
        lots = self.conn.execute(
            """
            SELECT id, qty_remaining FROM rm_stock_lots
            WHERE raw_material_id = ? AND qty_remaining > 1e-12
            ORDER BY received_date ASC, created_at ASC, id ASC
            """,
            (raw_material_id,),
        ).fetchall()
        for lot_row in lots:
            if need <= 1e-12:
                break
            lid = int(lot_row["id"])
            rem = float(lot_row["qty_remaining"])
            take = min(rem, need)
            new_rem = rem - take
            self.conn.execute(
                """
                UPDATE rm_stock_lots
                SET qty_remaining = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (new_rem, lid),
            )
            need -= take
        if need > 1e-9:
            raise ValueError("Not enough quantity on existing lots to reduce on-hand that far")

    def delete_rm_stock_lot(self, lot_id: int) -> None:
        """Permanently remove the lot row (hard delete, not soft delete / trash)."""
        lot = self.conn.execute(
            "SELECT production_batch_id FROM rm_stock_lots WHERE id = ?", (int(lot_id),)
        ).fetchone()
        if lot is None:
            raise ValueError("Lot not found")
        if lot["production_batch_id"] is not None:
            raise ValueError(
                "This lot is production batch output stock. Change or clear yield on "
                "Production → Batch costing (or delete the batch) instead of removing the lot here."
            )
        n = self.conn.execute(
            "SELECT COUNT(*) AS c FROM batch_rm_consumption WHERE rm_stock_lot_id = ?",
            (int(lot_id),),
        ).fetchone()
        if n is not None and int(n["c"] or 0) > 0:
            raise ValueError(
                "This lot cannot be removed because it is used on one or more production batch "
                "consumption lines. Open Production batches, delete those consumption lines "
                "(or delete the whole batch), then try again."
            )
        cur = self.conn.execute("DELETE FROM rm_stock_lots WHERE id = ?", (int(lot_id),))
        if cur.rowcount == 0:
            raise ValueError("Lot not found")

    # ---- production batches & RM consumption (Phase 4–5) ----
    def create_production_batch(
        self,
        batch_no: str,
        product_item_id: int,
        batch_date: date,
        notes: str = "",
    ) -> tuple[int, str]:
        ok = self.conn.execute(
            "SELECT 1 FROM items WHERE id = ? AND is_deleted = 0",
            (int(product_item_id),),
        ).fetchone()
        if ok is None:
            raise ValueError("Product not found or removed from master")
        bn = normalize_batch_no(batch_no)
        code = format_batch_code(batch_no, batch_date)
        dup = self.conn.execute(
            "SELECT 1 FROM production_batches WHERE batch_code = ?", (code,)
        ).fetchone()
        if dup is not None:
            raise ValueError(
                "That batch number and date would repeat an existing batch code. "
                "Use a different batch number (or change the date)."
            )
        cur = self.conn.execute(
            """
            INSERT INTO production_batches(batch_code, batch_no, product_item_id, batch_date, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                code,
                bn,
                int(product_item_id),
                _iso(batch_date),
                (notes or "").strip() or None,
            ),
        )
        bid = int(cur.lastrowid)
        pn = self.conn.execute(
            "SELECT name FROM items WHERE id = ?", (int(product_item_id),)
        ).fetchone()
        pname = str(pn["name"]) if pn else ""
        self.audit_log_append(
            action="production_batch_created",
            entity_type="production_batch",
            entity_id=bid,
            detail=f"batch_code={code}; product={pname}; batch_date={_iso(batch_date)}",
        )
        return bid, code

    def list_production_batches(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT
                  b.id,
                  b.batch_code,
                  b.batch_no,
                  b.batch_date,
                  b.notes,
                  b.batch_yield_kg,
                  b.conversion_cost_per_kg,
                  b.product_item_id,
                  i.name AS product_name
                FROM production_batches b
                JOIN items i ON i.id = b.product_item_id
                ORDER BY b.batch_date DESC, b.id DESC
                """
            ).fetchall()
        )

    def get_production_batch(self, batch_id: int) -> sqlite3.Row | None:
        return self.conn.execute(
            """
            SELECT
              b.id,
              b.batch_code,
              b.batch_no,
              b.batch_date,
              b.notes,
              b.batch_yield_kg,
              b.conversion_cost_per_kg,
              b.product_item_id,
              i.name AS product_name
            FROM production_batches b
            JOIN items i ON i.id = b.product_item_id
            WHERE b.id = ?
            """,
            (int(batch_id),),
        ).fetchone()

    def list_production_batches_for_product(self, product_item_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT id, batch_code, batch_date, notes
                FROM production_batches
                WHERE product_item_id = ?
                ORDER BY batch_date DESC, id DESC
                """,
                (int(product_item_id),),
            ).fetchall()
        )

    def batch_rm_material_cost(self, batch_id: int) -> float:
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(c.qty_consumed * l.unit_cost), 0) AS tot
            FROM batch_rm_consumption c
            JOIN rm_stock_lots l ON l.id = c.rm_stock_lot_id
            WHERE c.batch_id = ?
            """,
            (int(batch_id),),
        ).fetchone()
        return float(row["tot"] or 0) if row is not None else 0.0

    def update_production_batch_costing(
        self,
        batch_id: int,
        *,
        batch_yield_kg: float | None,
        conversion_cost_per_kg: float,
    ) -> None:
        b = self.get_production_batch(batch_id)
        if b is None:
            raise ValueError("Batch not found")
        cpk_in = float(conversion_cost_per_kg)
        if cpk_in < 0:
            raise ValueError("Conversion cost per kg cannot be negative")
        y = batch_yield_kg
        if y is not None:
            yf = float(y)
            if yf <= 0:
                raise ValueError("Yield must be > 0 when set")
        else:
            yf = None
        old_y = b["batch_yield_kg"]
        old_y_f = float(old_y) if old_y is not None and float(old_y) > 1e-12 else None
        bd = _d(str(b["batch_date"]))
        pid = int(b["product_item_id"])
        code = str(b["batch_code"])
        # Persist yield/conversion in its own transaction so a finished-goods sync failure
        # does not roll back costing (previously the whole UPDATE was lost if stock sync errored).
        with transaction(self.conn):
            self.conn.execute(
                """
                UPDATE production_batches
                SET batch_yield_kg = ?,
                    conversion_cost_per_kg = ?,
                    updated_at = datetime('now')
                WHERE id = ?
                """,
                (yf, cpk_in, int(batch_id)),
            )
        try:
            with transaction(self.conn):
                self._sync_fg_stock_after_yield_change(
                    batch_id=int(batch_id),
                    product_item_id=pid,
                    batch_date=bd,
                    batch_code=code,
                    old_yield_kg=old_y_f,
                    new_yield_kg=yf,
                )
        except Exception as e:
            raise ValueError(
                "Yield and conversion were saved, but finished-goods stock could not be updated:\n"
                f"{e}\n\n"
                "Check Seed Data: the product’s finished-good RM link, and that no other lot uses "
                "the same lot code as this batch."
            ) from e

    def _sync_fg_stock_after_yield_change(
        self,
        *,
        batch_id: int,
        product_item_id: int,
        batch_date: date,
        batch_code: str,
        old_yield_kg: float | None,
        new_yield_kg: float | None,
    ) -> None:
        """Upsert/delete RM lot row for batch output (finished goods), when RM is linked to product."""
        rm_id = self.raw_material_id_for_finished_product(product_item_id)
        if rm_id is None:
            return
        lot = self.conn.execute(
            """
            SELECT id, qty_received, qty_remaining
            FROM rm_stock_lots
            WHERE production_batch_id = ?
            """,
            (int(batch_id),),
        ).fetchone()

        if new_yield_kg is None or float(new_yield_kg) <= 1e-12:
            if lot is None:
                return
            sold = float(lot["qty_received"]) - float(lot["qty_remaining"])
            if sold > 1e-9:
                raise ValueError(
                    f"Cannot clear or zero yield: {sold:,.3f} kg from this batch is already invoiced. "
                    "Adjust or remove those invoice lines first."
                )
            self.conn.execute("DELETE FROM rm_stock_lots WHERE id = ?", (int(lot["id"]),))
            return

        new_y = float(new_yield_kg)
        cpk = self.production_batch_cost_per_kg(int(batch_id))
        uc = float(cpk) if cpk is not None else 0.0
        note = f"Batch output · {batch_code}"

        if lot is None:
            dup = self.conn.execute(
                "SELECT 1 FROM rm_stock_lots WHERE lot_code = ?", (batch_code,)
            ).fetchone()
            if dup is not None:
                raise ValueError(
                    f"Lot code {batch_code!r} is already used. Cannot create batch output lot."
                )
            self.conn.execute(
                """
                INSERT INTO rm_stock_lots(
                  raw_material_id, lot_code, received_date,
                  qty_received, qty_remaining, unit_cost, supplier_ref, notes, production_batch_id
                )
                VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (rm_id, batch_code, _iso(batch_date), new_y, new_y, uc, note, int(batch_id)),
            )
            return

        sold = float(lot["qty_received"]) - float(lot["qty_remaining"])
        new_rem = new_y - sold
        if new_rem < -1e-9:
            raise ValueError(
                f"Cannot reduce yield below quantity already invoiced from this batch ({sold:,.3f} kg)."
            )
        self.conn.execute(
            """
            UPDATE rm_stock_lots
            SET qty_received = ?, qty_remaining = ?, unit_cost = ?, notes = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (new_y, max(0.0, new_rem), uc, note, int(lot["id"])),
        )

    def finished_good_qty_remaining_for_batch(self, batch_id: int) -> float | None:
        """Qty remaining on the FG output lot for this batch, or None if there is no such lot."""
        row = self.conn.execute(
            """
            SELECT qty_remaining FROM rm_stock_lots
            WHERE production_batch_id = ?
            """,
            (int(batch_id),),
        ).fetchone()
        if row is None:
            return None
        return float(row["qty_remaining"])

    def production_batch_cost_per_kg(self, batch_id: int) -> float | None:
        """RM cost spread over yield + conversion ₹/kg when yield is set; else None."""
        b = self.get_production_batch(batch_id)
        if b is None:
            return None
        y = b["batch_yield_kg"]
        if y is None or float(y) <= 1e-12:
            return None
        rm = self.batch_rm_material_cost(batch_id)
        conv_pu = float(b["conversion_cost_per_kg"] or 0)
        return rm / float(y) + conv_pu

    def invoice_line_cogs_amount(self, qty: float, production_batch_id: int | None) -> float | None:
        """COGS for qty sold from batch (₹), if batch has cost/kg."""
        if production_batch_id is None:
            return None
        cpk = self.production_batch_cost_per_kg(int(production_batch_id))
        if cpk is None:
            return None
        return float(qty) * cpk

    def list_rm_lots_with_remaining(self, raw_material_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT
                  l.id,
                  l.lot_code,
                  l.qty_remaining,
                  l.received_date,
                  r.short_code AS rm_code,
                  r.unit AS unit
                FROM rm_stock_lots l
                JOIN raw_materials r ON r.id = l.raw_material_id AND r.is_deleted = 0
                WHERE l.raw_material_id = ? AND l.qty_remaining > 1e-9
                  AND l.production_batch_id IS NULL
                ORDER BY l.received_date ASC, l.created_at ASC, l.id ASC
                """,
                (int(raw_material_id),),
            ).fetchall()
        )

    def list_batch_rm_consumption(self, batch_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT
                  c.id,
                  c.batch_id,
                  c.rm_stock_lot_id,
                  c.raw_material_id,
                  c.qty_consumed,
                  c.source,
                  l.lot_code,
                  r.short_code AS rm_code,
                  r.unit AS unit
                FROM batch_rm_consumption c
                JOIN rm_stock_lots l ON l.id = c.rm_stock_lot_id
                JOIN raw_materials r ON r.id = c.raw_material_id AND r.is_deleted = 0
                WHERE c.batch_id = ?
                ORDER BY c.id ASC
                """,
                (int(batch_id),),
            ).fetchall()
        )

    def _restore_lot_qty(self, lot_id: int, qty: float) -> None:
        q = float(qty)
        row = self.conn.execute(
            "SELECT qty_remaining, qty_received FROM rm_stock_lots WHERE id = ?",
            (int(lot_id),),
        ).fetchone()
        if row is None:
            raise ValueError("Lot not found")
        new_rem = float(row["qty_remaining"]) + q
        if new_rem - float(row["qty_received"]) > 1e-9:
            raise ValueError("Cannot restore: would exceed original received quantity on lot")
        self.conn.execute(
            """
            UPDATE rm_stock_lots
            SET qty_remaining = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (new_rem, int(lot_id)),
        )

    def _reduce_lot_qty(self, lot_id: int, qty: float) -> None:
        q = float(qty)
        row = self.conn.execute(
            "SELECT qty_remaining FROM rm_stock_lots WHERE id = ?",
            (int(lot_id),),
        ).fetchone()
        if row is None:
            raise ValueError("Lot not found")
        rem = float(row["qty_remaining"])
        if rem + 1e-12 < q:
            raise ValueError("Not enough quantity remaining on this lot")
        self.conn.execute(
            """
            UPDATE rm_stock_lots
            SET qty_remaining = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (rem - q, int(lot_id)),
        )

    def add_batch_consumption_manual(
        self,
        batch_id: int,
        rm_stock_lot_id: int,
        qty: float,
        *,
        raw_material_id: int | None = None,
    ) -> int:
        q = float(qty)
        if q <= 0:
            raise ValueError("Quantity must be > 0")
        b = self.get_production_batch(batch_id)
        if b is None:
            raise ValueError("Batch not found")
        with transaction(self.conn):
            row = self.conn.execute(
                """
                SELECT l.raw_material_id, l.qty_remaining, l.production_batch_id
                FROM rm_stock_lots l
                JOIN raw_materials r ON r.id = l.raw_material_id AND r.is_deleted = 0
                WHERE l.id = ?
                """,
                (int(rm_stock_lot_id),),
            ).fetchone()
            if row is None:
                raise ValueError("Lot not found or raw material inactive")
            if row["production_batch_id"] is not None:
                raise ValueError(
                    "This lot is finished output from a production batch; it cannot be used as RM consumption."
                )
            rm_id = int(row["raw_material_id"])
            if raw_material_id is not None and int(raw_material_id) != rm_id:
                raise ValueError("Selected lot does not belong to the chosen raw material")
            self._reduce_lot_qty(int(rm_stock_lot_id), q)
            cur = self.conn.execute(
                """
                INSERT INTO batch_rm_consumption(
                  batch_id, rm_stock_lot_id, raw_material_id, qty_consumed, source
                )
                VALUES (?, ?, ?, ?, 'manual')
                """,
                (int(batch_id), int(rm_stock_lot_id), rm_id, q),
            )
            return int(cur.lastrowid)

    def add_batch_consumption_fifo(self, batch_id: int, raw_material_id: int, qty: float) -> list[int]:
        q = float(qty)
        if q <= 0:
            raise ValueError("Quantity must be > 0")
        if self.get_production_batch(batch_id) is None:
            raise ValueError("Batch not found")
        line_ids: list[int] = []
        with transaction(self.conn):
            need = q
            lots = self.conn.execute(
                """
                SELECT l.id, l.qty_remaining
                FROM rm_stock_lots l
                JOIN raw_materials r ON r.id = l.raw_material_id AND r.is_deleted = 0
                WHERE l.raw_material_id = ? AND l.qty_remaining > 1e-9
                  AND l.production_batch_id IS NULL
                ORDER BY l.received_date ASC, l.created_at ASC, l.id ASC
                """,
                (int(raw_material_id),),
            ).fetchall()
            for lot_row in lots:
                if need <= 1e-12:
                    break
                lid = int(lot_row["id"])
                rem = float(lot_row["qty_remaining"])
                take = min(rem, need)
                self._reduce_lot_qty(lid, take)
                cur = self.conn.execute(
                    """
                    INSERT INTO batch_rm_consumption(
                      batch_id, rm_stock_lot_id, raw_material_id, qty_consumed, source
                    )
                    VALUES (?, ?, ?, ?, 'fifo')
                    """,
                    (int(batch_id), lid, int(raw_material_id), take),
                )
                line_ids.append(int(cur.lastrowid))
                need -= take
            if need > 1e-9:
                raise ValueError("Not enough stock on lots (FIFO) for this raw material")
        return line_ids

    def remove_batch_consumption_line(self, line_id: int) -> None:
        with transaction(self.conn):
            row = self.conn.execute(
                """
                SELECT rm_stock_lot_id, qty_consumed FROM batch_rm_consumption WHERE id = ?
                """,
                (int(line_id),),
            ).fetchone()
            if row is None:
                raise ValueError("Consumption line not found")
            self._restore_lot_qty(int(row["rm_stock_lot_id"]), float(row["qty_consumed"]))
            self.conn.execute("DELETE FROM batch_rm_consumption WHERE id = ?", (int(line_id),))

    def delete_production_batch(self, batch_id: int) -> None:
        with transaction(self.conn):
            if self.get_production_batch(batch_id) is None:
                raise ValueError("Batch not found")
            lines = self.conn.execute(
                "SELECT rm_stock_lot_id, qty_consumed FROM batch_rm_consumption WHERE batch_id = ?",
                (int(batch_id),),
            ).fetchall()
            for ln in lines:
                self._restore_lot_qty(int(ln["rm_stock_lot_id"]), float(ln["qty_consumed"]))
            self.conn.execute(
                "DELETE FROM batch_rm_consumption WHERE batch_id = ?", (int(batch_id),)
            )
            self.conn.execute("DELETE FROM production_batches WHERE id = ?", (int(batch_id),))

    def soft_delete_raw_material(self, raw_material_id: int) -> None:
        oh = self.raw_material_on_hand(raw_material_id)
        if oh > 0.00001:
            raise ValueError("Cannot remove raw material while stock remains. Use stock adjustments later or consume in batches.")
        self.conn.execute(
            """
            UPDATE raw_materials
            SET is_deleted = 1, deleted_at = datetime('now'), updated_at = datetime('now')
            WHERE id = ? AND is_deleted = 0
            """,
            (raw_material_id,),
        )

    def restore_raw_material(self, raw_material_id: int) -> None:
        self.conn.execute(
            """
            UPDATE raw_materials
            SET is_deleted = 0, deleted_at = NULL, updated_at = datetime('now')
            WHERE id = ? AND is_deleted = 1
            """,
            (raw_material_id,),
        )

    def list_deleted_raw_materials(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT id, name, short_code, deleted_at
                FROM raw_materials
                WHERE is_deleted = 1
                ORDER BY deleted_at DESC, short_code
                """
            ).fetchall()
        )

    @staticmethod
    def fy_start_year(d: date) -> int:
        # FY starts 1st April: 2025-04-01..2026-03-31 => fy_start_year=2025
        return d.year if d.month >= 4 else (d.year - 1)

    def get_next_invoice_serial(self, invoice_date: date) -> int:
        """
        Returns next invoice serial within the financial year of `invoice_date`.
        Looks at existing `invoice_no` values that are purely numeric like '001'.
        """
        fy = Repo.fy_start_year(invoice_date)
        fy_start = date(fy, 4, 1).isoformat()
        fy_end = date(fy + 1, 3, 31).isoformat()

        rows = self.conn.execute(
            """
            SELECT invoice_no
            FROM invoices
            WHERE is_deleted = 0
              AND invoice_date >= ? AND invoice_date <= ?
            """,
            (fy_start, fy_end),
        ).fetchall()

        max_n = 0
        for r in rows:
            s = str(r["invoice_no"] or "").strip()
            if not s.isdigit():
                continue
            try:
                max_n = max(max_n, int(s))
            except Exception:
                pass
        return max_n + 1

    # ---- settings (meta table) ----
    def get_setting(self, key: str, default: str = "") -> str:
        row = self.conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        if row is None:
            return default
        return str(row["value"])

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            """
            INSERT INTO meta(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )

    # ---- audit trail (append-only events; desktop single-operator) ----
    def audit_log_append(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: int | None = None,
        detail: str = "",
    ) -> None:
        d = (detail or "").strip().replace("\r\n", "\n").replace("\r", "\n")
        if len(d) > 4000:
            d = d[:3997] + "..."
        self.conn.execute(
            """
            INSERT INTO audit_log(created_at, action, entity_type, entity_id, detail, operator)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                now_ist_wall_clock(),
                (action or "").strip()[:160],
                (entity_type or "").strip()[:80],
                entity_id,
                d,
                audit_operator_name(),
            ),
        )

    def list_audit_log(self, *, limit: int = 800) -> list[AuditLogRow]:
        lim = max(1, min(int(limit), 5000))
        rows = self.conn.execute(
            """
            SELECT id, created_at, action, entity_type, entity_id, detail,
                   COALESCE(operator, '') AS operator
            FROM audit_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (lim,),
        ).fetchall()
        out: list[AuditLogRow] = []
        for r in rows:
            eid = r["entity_id"]
            out.append(
                AuditLogRow(
                    id=int(r["id"]),
                    created_at=str(r["created_at"]),
                    action=str(r["action"]),
                    entity_type=str(r["entity_type"]),
                    entity_id=int(eid) if eid is not None else None,
                    detail=str(r["detail"] or ""),
                    operator=str(r["operator"] or ""),
                )
            )
        return out

    # ---- invoices ----
    def create_invoice(
        self,
        customer_id: int,
        invoice_no: str,
        invoice_date: date,
        total_after_tax: float,
        excel_path: str | None = None,
    ) -> int:
        invoice_no = invoice_no.strip()
        if not invoice_no:
            raise ValueError("Invoice no required")
        if total_after_tax <= 0:
            raise ValueError("Total must be > 0")

        cust = self.conn.execute(
            "SELECT credit_days FROM customers WHERE id = ? AND is_deleted = 0", (customer_id,)
        ).fetchone()
        if cust is None:
            raise ValueError("Customer not found")

        due_date = compute_due_date(invoice_date, int(cust["credit_days"]))
        cur = self.conn.execute(
            """
            INSERT INTO invoices(customer_id, invoice_no, invoice_date, due_date, total_after_tax, excel_path)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                customer_id,
                invoice_no,
                _iso(invoice_date),
                _iso(due_date),
                float(total_after_tax),
                (excel_path or "").strip() or None,
            ),
        )
        inv_id = int(cur.lastrowid)
        cnm = self.conn.execute(
            "SELECT name FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        cname = str(cnm["name"]) if cnm else ""
        self.audit_log_append(
            action="invoice_created",
            entity_type="invoice",
            entity_id=inv_id,
            detail=(
                f"customer={cname}; invoice_no={invoice_no}; "
                f"date={_iso(invoice_date)}; total={float(total_after_tax):.2f}"
            ),
        )
        return inv_id

    def validate_invoice_fg_stock_plan(self, lines: list[dict]) -> str | None:
        """
        Simulate finished-goods deductions in line order (batch-specific lot first, else FIFO by RM).
        Returns an error message if any line cannot be satisfied, else None.
        """
        ordered = sorted(lines, key=lambda x: int(x.get("line_no") or 0))
        rows = list(
            self.conn.execute(
                """
                SELECT l.id, l.raw_material_id, l.qty_remaining, l.production_batch_id
                FROM rm_stock_lots l
                JOIN raw_materials r ON r.id = l.raw_material_id AND r.is_deleted = 0
                WHERE l.qty_remaining > 1e-9
                ORDER BY l.raw_material_id, l.received_date ASC, l.created_at ASC, l.id ASC
                """
            ).fetchall()
        )
        rem: dict[int, float] = {int(r["id"]): float(r["qty_remaining"]) for r in rows}
        fifo_lists: dict[int, list[int]] = {}
        for r in rows:
            rid = int(r["raw_material_id"])
            fifo_lists.setdefault(rid, []).append(int(r["id"]))
        lot_by_batch: dict[int, int] = {}
        for r in rows:
            pb = r["production_batch_id"]
            if pb is not None:
                lot_by_batch[int(pb)] = int(r["id"])

        for line in ordered:
            ln = int(line.get("line_no") or 0)
            desc = str(line.get("description") or "").strip()
            qty = float(line.get("qty") or 0)
            if qty <= 1e-12:
                continue
            pb = line.get("production_batch_id")
            pb_id = int(pb) if pb is not None else None
            if pb_id is not None:
                lid = lot_by_batch.get(pb_id)
                if lid is None:
                    return (
                        f"Line {ln}: batch has no finished-goods stock lot ({qty:,.3f} kg on this line). "
                        "Save yield on Production → Batch costing and link the FG RM to this product, "
                        "or set Batch to “— none —”."
                    )
                if rem.get(lid, 0) + 1e-12 < qty:
                    return (
                        f"Line {ln}: not enough stock for the selected batch "
                        f"({rem.get(lid, 0):,.3f} kg on hand, line needs {qty:,.3f} kg)."
                    )
                rem[lid] -= qty
                continue
            raw_pi = line.get("product_item_id")
            if raw_pi is not None:
                iid = int(raw_pi)
            else:
                iid = self.resolve_item_id_from_description(desc)
            if iid is None:
                continue
            rm_id = self.raw_material_id_for_finished_product(int(iid))
            if rm_id is None:
                continue
            need = qty
            for lid in fifo_lists.get(int(rm_id), []):
                if need <= 1e-12:
                    break
                available = rem.get(lid, 0)
                if available <= 1e-12:
                    continue
                take = min(available, need)
                rem[lid] -= take
                need -= take
            if need > 1e-9:
                rrow = self.conn.execute(
                    "SELECT short_code FROM raw_materials WHERE id = ?", (int(rm_id),)
                ).fetchone()
                sc = str(rrow["short_code"]) if rrow else str(rm_id)
                return (
                    f"Line {ln}: finished good “{sc}” needs {qty:,.3f} kg from stock (FIFO) "
                    f"but not enough remains after earlier lines (short by {need:,.3f} kg). "
                    "Lower quantity, add stock, or assign batches."
                )
        return None

    def add_invoice_items(self, invoice_id: int, lines: list[dict]) -> None:
        ordered = sorted(lines, key=lambda x: int(x.get("line_no") or 0))
        for line in ordered:
            pb = line.get("production_batch_id")
            pb_id = int(pb) if pb is not None else None
            qty = float(line.get("qty") or 0)
            desc = str(line.get("description") or "").strip()
            if pb_id is not None and qty > 1e-12:
                fg = self.conn.execute(
                    """
                    SELECT id, qty_remaining
                    FROM rm_stock_lots
                    WHERE production_batch_id = ?
                    """,
                    (pb_id,),
                ).fetchone()
                if fg is None:
                    raise ValueError(
                        "An invoice line is linked to a batch that has no finished-goods stock lot. "
                        "Save yield on Production → Batch costing, and in Setup → Seed Data link the "
                        "finished-good RM row (e.g. LP750) to that product."
                    )
                rem = float(fg["qty_remaining"])
                if rem + 1e-12 < qty:
                    raise ValueError(
                        f"Not enough finished goods for batch-linked line ({rem:,.3f} kg on hand, "
                        f"invoice line needs {qty:,.3f} kg)."
                    )
                self._reduce_lot_qty(int(fg["id"]), qty)
            elif pb_id is None and qty > 1e-12:
                raw_pi = line.get("product_item_id")
                if raw_pi is not None:
                    iid = int(raw_pi)
                else:
                    iid = self.resolve_item_id_from_description(desc)
                if iid is not None:
                    rm_id = self.raw_material_id_for_finished_product(int(iid))
                    if rm_id is not None:
                        self.reduce_raw_material_stock_fifo(int(rm_id), qty)
            self.conn.execute(
                """
                INSERT INTO invoice_items(
                  invoice_id, line_no, description, hsn, qty, unit, rate, amount, production_batch_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice_id,
                    int(line.get("line_no") or 0),
                    desc,
                    (str(line.get("hsn") or "").strip() or None),
                    line.get("qty"),
                    (str(line.get("unit") or "").strip() or None),
                    line.get("rate"),
                    line.get("amount"),
                    pb_id,
                ),
            )

    # ---- payments ----
    def create_payment(
        self,
        customer_id: int,
        payment_date: date,
        amount: float,
        mode: str = "",
        reference: str = "",
        notes: str = "",
    ) -> int:
        if amount <= 0:
            raise ValueError("Payment amount must be > 0")

        cur = self.conn.execute(
            """
            INSERT INTO payments(customer_id, payment_date, amount, mode, reference, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (customer_id, _iso(payment_date), float(amount), mode.strip(), reference.strip(), notes.strip()),
        )
        payment_id = int(cur.lastrowid)
        self.allocate_payment_fifo(payment_id=payment_id, customer_id=customer_id)
        cnm = self.conn.execute(
            "SELECT name FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        cname = str(cnm["name"]) if cnm else ""
        ref_s = reference.strip()
        self.audit_log_append(
            action="payment_created",
            entity_type="payment",
            entity_id=payment_id,
            detail=(
                f"customer={cname}; amount={float(amount):.2f}; "
                f"date={_iso(payment_date)}; mode={mode.strip() or '—'}"
                + (f"; ref={ref_s}" if ref_s else "")
            ),
        )
        return payment_id

    def allocate_payment_fifo(self, payment_id: int, customer_id: int) -> None:
        pay = self.conn.execute(
            "SELECT amount FROM payments WHERE id = ? AND is_deleted = 0", (payment_id,)
        ).fetchone()
        if pay is None:
            raise ValueError("Payment not found")

        allocated = self.conn.execute(
            "SELECT COALESCE(SUM(amount),0) AS s FROM allocations WHERE payment_id = ?",
            (payment_id,),
        ).fetchone()["s"]
        remaining = float(pay["amount"]) - float(allocated)
        if remaining <= 0:
            return

        invoices = self.conn.execute(
            """
            SELECT invoice_id, outstanding
            FROM invoice_balances
            WHERE customer_id = ? AND outstanding > 0.00001
            ORDER BY due_date ASC, invoice_date ASC, invoice_no ASC
            """,
            (customer_id,),
        ).fetchall()

        for inv in invoices:
            if remaining <= 0:
                break
            inv_id = int(inv["invoice_id"])
            inv_out = float(inv["outstanding"])
            to_apply = min(inv_out, remaining)

            # If an allocation row already exists for this (payment, invoice), add to it.
            existing = self.conn.execute(
                "SELECT id, amount FROM allocations WHERE payment_id = ? AND invoice_id = ?",
                (payment_id, inv_id),
            ).fetchone()
            if existing is None:
                self.conn.execute(
                    "INSERT INTO allocations(payment_id, invoice_id, amount) VALUES (?, ?, ?)",
                    (payment_id, inv_id, to_apply),
                )
            else:
                self.conn.execute(
                    "UPDATE allocations SET amount = ? WHERE id = ?",
                    (float(existing["amount"]) + to_apply, int(existing["id"])),
                )
            remaining -= to_apply

    # ---- dues ----
    def due_rows(
        self,
        today: date,
        only_due_today: bool = False,
        only_overdue: bool = False,
        *,
        due_from: date | None = None,
        due_to: date | None = None,
    ) -> list[DueRow]:
        if only_due_today and only_overdue:
            raise ValueError("Choose only one filter")

        where = ["ib.outstanding > 0.00001"]
        params: list[object] = []

        if due_from is not None:
            where.append("ib.due_date >= ?")
            params.append(_iso(due_from))
        if due_to is not None:
            where.append("ib.due_date <= ?")
            params.append(_iso(due_to))

        if only_due_today:
            where.append("ib.due_date = ?")
            params.append(_iso(today))
        if only_overdue:
            where.append("ib.due_date < ?")
            params.append(_iso(today))

        sql = f"""
        SELECT
          c.id AS customer_id,
          c.name AS customer_name,
          ib.invoice_id,
          ib.invoice_no,
          ib.invoice_date,
          ib.due_date,
          ib.outstanding,
          i.excel_path AS excel_path
        FROM invoice_balances ib
        JOIN customers c ON c.id = ib.customer_id
        JOIN invoices i ON i.id = ib.invoice_id AND i.is_deleted = 0
        WHERE {' AND '.join(where)}
        ORDER BY ib.due_date ASC, c.name ASC, ib.invoice_no ASC
        """
        rows = self.conn.execute(sql, params).fetchall()
        out: list[DueRow] = []
        for r in rows:
            due = _d(r["due_date"])
            days_overdue = (today - due).days
            xp = r["excel_path"]
            out.append(
                DueRow(
                    customer_id=int(r["customer_id"]),
                    customer_name=str(r["customer_name"]),
                    invoice_id=int(r["invoice_id"]),
                    invoice_no=str(r["invoice_no"]),
                    invoice_date=_d(r["invoice_date"]),
                    due_date=due,
                    outstanding=float(r["outstanding"]),
                    days_overdue=max(0, days_overdue),
                    excel_path=str(xp).strip() if xp else None,
                )
            )
        return out

    # ---- ledger ----
    @dataclass(frozen=True)
    class LedgerRow:
        entry_date: date
        entry_type: str  # INVOICE|PAYMENT
        ref: str
        debit: float
        credit: float
        balance: float
        invoice_id: int | None = None
        excel_path: str | None = None
        payment_id: int | None = None

    def ledger_net_before(self, customer_id: int, before_date: date) -> float:
        """Sum(debit - credit) for movements on dates strictly before `before_date`."""
        rows = self.conn.execute(
            """
            SELECT entry_date, debit, credit
            FROM (
              SELECT invoice_date AS entry_date, total_after_tax AS debit, 0.0 AS credit
              FROM invoices
              WHERE customer_id = ? AND is_deleted = 0
              UNION ALL
              SELECT payment_date AS entry_date, 0.0 AS debit, amount AS credit
              FROM payments
              WHERE customer_id = ? AND is_deleted = 0
            )
            ORDER BY entry_date ASC
            """,
            (customer_id, customer_id),
        ).fetchall()
        total = 0.0
        for r in rows:
            ed = _d(r["entry_date"])
            if ed < before_date:
                total += float(r["debit"]) - float(r["credit"])
            else:
                break
        return total

    def ledger_rows(
        self,
        customer_id: int,
        *,
        entry_from: date | None = None,
        entry_to: date | None = None,
    ) -> list["Repo.LedgerRow"]:
        # Debit: invoice total_after_tax
        # Credit: payment amount (not allocations) — matches "Credit for payments" requirement.
        rows = self.conn.execute(
            """
            SELECT entry_date, entry_type, ref, debit, credit, invoice_id, excel_path, payment_id
            FROM (
              SELECT
                invoice_date AS entry_date,
                'INVOICE' AS entry_type,
                invoice_no AS ref,
                total_after_tax AS debit,
                0.0 AS credit,
                id AS invoice_id,
                excel_path,
                NULL AS payment_id
              FROM invoices
              WHERE customer_id = ? AND is_deleted = 0

              UNION ALL

              SELECT
                payment_date AS entry_date,
                'PAYMENT' AS entry_type,
                COALESCE(reference, '') AS ref,
                0.0 AS debit,
                amount AS credit,
                NULL AS invoice_id,
                NULL AS excel_path,
                id AS payment_id
              FROM payments
              WHERE customer_id = ? AND is_deleted = 0
            )
            ORDER BY entry_date ASC, entry_type ASC, ref ASC
            """,
            (customer_id, customer_id),
        ).fetchall()

        movements: list[
            tuple[date, str, str, float, float, int | None, str | None, int | None]
        ] = []
        for r in rows:
            iid = r["invoice_id"]
            xp = r["excel_path"]
            pid = r["payment_id"]
            movements.append(
                (
                    _d(r["entry_date"]),
                    str(r["entry_type"]),
                    str(r["ref"] or ""),
                    float(r["debit"]),
                    float(r["credit"]),
                    int(iid) if iid is not None else None,
                    str(xp).strip() if xp else None,
                    int(pid) if pid is not None else None,
                )
            )

        opening = 0.0
        if entry_from is not None:
            for ed, _, _, debit, credit, _, _, _ in movements:
                if ed < entry_from:
                    opening += debit - credit
                else:
                    break

        balance = opening
        out: list[Repo.LedgerRow] = []
        for ed, et, ref, debit, credit, inv_id, xl, pay_id in movements:
            if entry_from is not None and ed < entry_from:
                continue
            if entry_to is not None and ed > entry_to:
                continue
            balance += debit - credit
            out.append(
                Repo.LedgerRow(
                    entry_date=ed,
                    entry_type=et,
                    ref=ref,
                    debit=debit,
                    credit=credit,
                    balance=balance,
                    invoice_id=inv_id,
                    excel_path=xl,
                    payment_id=pay_id,
                )
            )
        return out

    def due_customer_rows(
        self,
        today: date,
        only_due_today: bool = False,
        only_overdue: bool = False,
        *,
        due_from: date | None = None,
        due_to: date | None = None,
    ) -> list[CustomerDueRow]:
        if only_due_today and only_overdue:
            raise ValueError("Choose only one filter")

        where = ["ib.outstanding > 0.00001"]
        params: list[object] = []

        if due_from is not None:
            where.append("ib.due_date >= ?")
            params.append(_iso(due_from))
        if due_to is not None:
            where.append("ib.due_date <= ?")
            params.append(_iso(due_to))

        if only_due_today:
            where.append("ib.due_date = ?")
            params.append(_iso(today))
        if only_overdue:
            where.append("ib.due_date < ?")
            params.append(_iso(today))

        sql = f"""
        SELECT
          c.id AS customer_id,
          c.name AS customer_name,
          SUM(ib.outstanding) AS outstanding,
          MIN(ib.due_date) AS oldest_due_date,
          COUNT(*) AS invoice_count
        FROM invoice_balances ib
        JOIN customers c ON c.id = ib.customer_id
        WHERE {' AND '.join(where)}
        GROUP BY c.id
        ORDER BY MIN(ib.due_date) ASC, c.name ASC
        """
        rows = self.conn.execute(sql, params).fetchall()
        out: list[CustomerDueRow] = []
        for r in rows:
            oldest_due = _d(r["oldest_due_date"])
            days_overdue = (today - oldest_due).days
            out.append(
                CustomerDueRow(
                    customer_id=int(r["customer_id"]),
                    customer_name=str(r["customer_name"]),
                    outstanding=float(r["outstanding"]),
                    oldest_due_date=oldest_due,
                    invoice_count=int(r["invoice_count"]),
                    days_overdue=max(0, days_overdue),
                )
            )
        return out

    def receivables_aging_report(
        self, today: date
    ) -> tuple[ReceivablesAgingTotals, list[CustomerAgingRow]]:
        """
        Outstanding receivables by bucket (due date vs `today`), customer-wise + totals.
        Buckets: not yet due (current), 1–30 / 31–60 / 61–90 / 90+ days past due.
        """
        rows = self.conn.execute(
            """
            SELECT c.id AS customer_id, c.name AS customer_name,
                   ib.outstanding AS outstanding, ib.due_date AS due_date
            FROM invoice_balances ib
            JOIN customers c ON c.id = ib.customer_id AND c.is_deleted = 0
            JOIN invoices i ON i.id = ib.invoice_id AND i.is_deleted = 0
            WHERE ib.outstanding > 0.00001
            ORDER BY c.name ASC, ib.due_date ASC
            """
        ).fetchall()

        agg: dict[int, dict[str, float]] = {}
        names: dict[int, str] = {}
        grand = {"current": 0.0, "p1_30": 0.0, "p31_60": 0.0, "p61_90": 0.0, "p90_plus": 0.0}

        for r in rows:
            cid = int(r["customer_id"])
            names[cid] = str(r["customer_name"])
            amt = float(r["outstanding"])
            due = _d(str(r["due_date"]))
            bucket = receivable_aging_bucket(due, today)
            if cid not in agg:
                agg[cid] = {
                    "current": 0.0,
                    "p1_30": 0.0,
                    "p31_60": 0.0,
                    "p61_90": 0.0,
                    "p90_plus": 0.0,
                }
            agg[cid][bucket] += amt
            grand[bucket] += amt

        cust_rows: list[CustomerAgingRow] = []
        for cid in sorted(names.keys(), key=lambda x: names[x].lower()):
            b = agg[cid]
            cust_rows.append(
                CustomerAgingRow(
                    customer_id=cid,
                    customer_name=names[cid],
                    current=b["current"],
                    past_1_30=b["p1_30"],
                    past_31_60=b["p31_60"],
                    past_61_90=b["p61_90"],
                    past_90_plus=b["p90_plus"],
                )
            )

        totals = ReceivablesAgingTotals(
            current=grand["current"],
            past_1_30=grand["p1_30"],
            past_31_60=grand["p31_60"],
            past_61_90=grand["p61_90"],
            past_90_plus=grand["p90_plus"],
        )
        return totals, cust_rows

    # ---- dashboard ----
    def dashboard_summary(self, today: date) -> DashboardSummary:
        iso_t = _iso(today)
        counts = self.conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM customers WHERE is_deleted = 0) AS n_cust,
              (SELECT COUNT(*) FROM items WHERE is_deleted = 0) AS n_items,
              (SELECT COUNT(*) FROM raw_materials WHERE is_deleted = 0) AS n_rm,
              (SELECT COUNT(*) FROM production_batches) AS n_batches,
              (SELECT COUNT(*) FROM invoices WHERE is_deleted = 0) AS n_inv,
              (SELECT COUNT(*) FROM payments WHERE is_deleted = 0) AS n_pay
            """
        ).fetchone()
        agg = self.conn.execute(
            """
            SELECT
              COALESCE(SUM(ib.outstanding), 0) AS tot,
              SUM(CASE WHEN ib.due_date = ? THEN 1 ELSE 0 END) AS due_today,
              SUM(CASE WHEN ib.due_date < ? THEN 1 ELSE 0 END) AS overdue
            FROM invoice_balances ib
            WHERE ib.outstanding > 0.00001
            """,
            (iso_t, iso_t),
        ).fetchone()
        ym = today.strftime("%Y-%m")
        y_str = str(today.year)
        sales_m = self.conn.execute(
            """
            SELECT COALESCE(SUM(COALESCE(li.amount, COALESCE(li.qty, 0) * COALESCE(li.rate, 0), 0)), 0) AS s
            FROM invoice_items li
            JOIN invoices i ON i.id = li.invoice_id AND i.is_deleted = 0
            WHERE strftime('%Y-%m', i.invoice_date) = ?
            """,
            (ym,),
        ).fetchone()
        sales_y = self.conn.execute(
            """
            SELECT COALESCE(SUM(COALESCE(li.amount, COALESCE(li.qty, 0) * COALESCE(li.rate, 0), 0)), 0) AS s
            FROM invoice_items li
            JOIN invoices i ON i.id = li.invoice_id AND i.is_deleted = 0
            WHERE strftime('%Y', i.invoice_date) = ?
            """,
            (y_str,),
        ).fetchone()
        pay_m = self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS s
            FROM payments
            WHERE is_deleted = 0 AND strftime('%Y-%m', payment_date) = ?
            """,
            (ym,),
        ).fetchone()
        pay_y = self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS s
            FROM payments
            WHERE is_deleted = 0 AND strftime('%Y', payment_date) = ?
            """,
            (y_str,),
        ).fetchone()
        mtd_ic = self.conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM invoices
            WHERE is_deleted = 0 AND strftime('%Y-%m', invoice_date) = ?
            """,
            (ym,),
        ).fetchone()
        ytd_ic = self.conn.execute(
            """
            SELECT COUNT(*) AS n
            FROM invoices
            WHERE is_deleted = 0 AND strftime('%Y', invoice_date) = ?
            """,
            (y_str,),
        ).fetchone()
        mtd_cogs = 0.0
        ytd_cogs = 0.0
        for r in self.list_invoice_gross_profits():
            if r.invoice_date.strftime("%Y-%m") == ym:
                mtd_cogs += r.cogs
            if r.invoice_date.strftime("%Y") == y_str:
                ytd_cogs += r.cogs
        mtd_sales = float(sales_m["s"] or 0)
        ytd_sales = float(sales_y["s"] or 0)
        return DashboardSummary(
            customer_count=int(counts["n_cust"]),
            item_count=int(counts["n_items"]),
            raw_material_count=int(counts["n_rm"] or 0),
            production_batch_count=int(counts["n_batches"] or 0),
            invoice_count=int(counts["n_inv"]),
            payment_count=int(counts["n_pay"]),
            total_outstanding=float(agg["tot"]),
            due_today_invoice_count=int(agg["due_today"] or 0),
            overdue_invoice_count=int(agg["overdue"] or 0),
            mtd_sales_ex_gst=mtd_sales,
            ytd_sales_ex_gst=ytd_sales,
            mtd_collections=float(pay_m["s"] or 0),
            ytd_collections=float(pay_y["s"] or 0),
            mtd_invoice_count=int(mtd_ic["n"] or 0),
            ytd_invoice_count=int(ytd_ic["n"] or 0),
            mtd_cogs=mtd_cogs,
            ytd_cogs=ytd_cogs,
            mtd_gross_profit=mtd_sales - mtd_cogs,
            ytd_gross_profit=ytd_sales - ytd_cogs,
        )

    def payments_total_in_date_range(self, d0: date, d1: date) -> float:
        """Sum payment amounts with ``payment_date`` in ``[d0, d1]`` (inclusive)."""
        if d0 > d1:
            d0, d1 = d1, d0
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) AS s
            FROM payments
            WHERE is_deleted = 0 AND payment_date >= ? AND payment_date <= ?
            """,
            (_iso(d0), _iso(d1)),
        ).fetchone()
        return float(row["s"] or 0)

    def list_invoice_gross_profits(self) -> list[InvoiceGrossProfit]:
        """Gross profit per invoice: taxable line totals minus batch COGS where computable."""
        cur = self.conn.execute(
            """
            SELECT i.id, i.invoice_no, i.invoice_date, i.total_after_tax,
                   c.name AS customer_name,
                   li.qty, li.rate, li.amount, li.production_batch_id
            FROM invoice_items li
            JOIN invoices i ON i.id = li.invoice_id AND i.is_deleted = 0
            JOIN customers c ON c.id = i.customer_id
            ORDER BY i.invoice_date ASC, i.id ASC, li.line_no ASC
            """
        )
        by_inv: dict[int, list[sqlite3.Row]] = defaultdict(list)
        headers: dict[int, tuple[str, date, float, str]] = {}
        for r in cur.fetchall():
            iid = int(r["id"])
            by_inv[iid].append(r)
            if iid not in headers:
                headers[iid] = (
                    str(r["invoice_no"]),
                    _d(str(r["invoice_date"])),
                    float(r["total_after_tax"] or 0),
                    str(r["customer_name"]),
                )
        cpk_cache: dict[int, float | None] = {}

        def _cpk(batch_id: int) -> float | None:
            if batch_id not in cpk_cache:
                cpk_cache[batch_id] = self.production_batch_cost_per_kg(batch_id)
            return cpk_cache[batch_id]

        out: list[InvoiceGrossProfit] = []
        for iid in sorted(headers.keys(), key=lambda k: (headers[k][1], k), reverse=True):
            inv_no, inv_date, total_after_tax, cust = headers[iid]
            revenue = 0.0
            cogs_sum = 0.0
            n_lines = 0
            n_cogs = 0
            for lr in by_inv[iid]:
                qty = float(lr["qty"] or 0)
                rate = float(lr["rate"] or 0)
                amt = lr["amount"]
                line_rev = float(amt) if amt is not None else qty * rate
                revenue += line_rev
                n_lines += 1
                pb = lr["production_batch_id"]
                if pb is not None:
                    cpk = _cpk(int(pb))
                    if cpk is not None and qty > 1e-12:
                        cogs_sum += qty * cpk
                        n_cogs += 1
            out.append(
                InvoiceGrossProfit(
                    invoice_id=iid,
                    invoice_no=inv_no,
                    invoice_date=inv_date,
                    customer_name=cust,
                    revenue_ex_gst=revenue,
                    total_after_tax=total_after_tax,
                    cogs=cogs_sum,
                    gross_profit=revenue - cogs_sum,
                    line_count=n_lines,
                    lines_with_cogs=n_cogs,
                    cogs_complete=n_lines > 0 and n_cogs == n_lines,
                )
            )
        return out

    def _payment_sums_by_month(self) -> dict[str, float]:
        d: dict[str, float] = {}
        for r in self.conn.execute(
            """
            SELECT strftime('%Y-%m', payment_date) AS ym, SUM(amount) AS s
            FROM payments
            WHERE is_deleted = 0
            GROUP BY ym
            """
        ):
            ym = str(r["ym"] or "")
            if ym:
                d[ym] = float(r["s"] or 0)
        return d

    def _payment_sums_by_year(self) -> dict[str, float]:
        d: dict[str, float] = {}
        for r in self.conn.execute(
            """
            SELECT strftime('%Y', payment_date) AS y, SUM(amount) AS s
            FROM payments
            WHERE is_deleted = 0
            GROUP BY y
            """
        ):
            y = str(r["y"] or "")
            if y:
                d[y] = float(r["s"] or 0)
        return d

    def analytics_monthly_rows(
        self,
        invoices: list[InvoiceGrossProfit] | None = None,
        *,
        include_payments: bool = True,
    ) -> list[AnalyticsMonthRow]:
        inv = invoices if invoices is not None else self.list_invoice_gross_profits()
        pay_m = self._payment_sums_by_month() if include_payments else {}
        agg: dict[str, dict[str, float]] = defaultdict(
            lambda: {
                "sales": 0.0,
                "bill": 0.0,
                "cogs": 0.0,
            }
        )
        for row in inv:
            ym = row.invoice_date.strftime("%Y-%m")
            a = agg[ym]
            a["sales"] += row.revenue_ex_gst
            a["bill"] += row.total_after_tax
            a["cogs"] += row.cogs
        keys = sorted(set(agg.keys()) | set(pay_m.keys()), reverse=True) if include_payments else sorted(agg.keys(), reverse=True)
        out: list[AnalyticsMonthRow] = []
        for ym in keys:
            a = agg.get(ym, {"sales": 0.0, "bill": 0.0, "cogs": 0.0})
            sales = float(a["sales"])
            bill = float(a["bill"])
            cogs = float(a["cogs"])
            est_gst = max(0.0, bill - sales)
            out.append(
                AnalyticsMonthRow(
                    year_month=ym,
                    sales_ex_gst=sales,
                    bill_total_after_tax=bill,
                    est_output_gst=est_gst,
                    payments_received=float(pay_m.get(ym, 0.0)),
                    cogs=cogs,
                    gross_profit=sales - cogs,
                )
            )
        return out

    def analytics_yearly_rows(
        self,
        invoices: list[InvoiceGrossProfit] | None = None,
        *,
        include_payments: bool = True,
    ) -> list[AnalyticsYearRow]:
        inv = invoices if invoices is not None else self.list_invoice_gross_profits()
        pay_y = self._payment_sums_by_year() if include_payments else {}
        agg: dict[str, dict[str, float]] = defaultdict(
            lambda: {
                "sales": 0.0,
                "bill": 0.0,
                "cogs": 0.0,
            }
        )
        for row in inv:
            y = row.invoice_date.strftime("%Y")
            a = agg[y]
            a["sales"] += row.revenue_ex_gst
            a["bill"] += row.total_after_tax
            a["cogs"] += row.cogs
        keys = sorted(set(agg.keys()) | set(pay_y.keys()), reverse=True) if include_payments else sorted(agg.keys(), reverse=True)
        out: list[AnalyticsYearRow] = []
        for y in keys:
            a = agg.get(y, {"sales": 0.0, "bill": 0.0, "cogs": 0.0})
            sales = float(a["sales"])
            bill = float(a["bill"])
            cogs = float(a["cogs"])
            est_gst = max(0.0, bill - sales)
            out.append(
                AnalyticsYearRow(
                    year=y,
                    sales_ex_gst=sales,
                    bill_total_after_tax=bill,
                    est_output_gst=est_gst,
                    payments_received=float(pay_y.get(y, 0.0)),
                    cogs=cogs,
                    gross_profit=sales - cogs,
                )
            )
        return out

    # ---- search ----
    def search_hits(self, query: str, *, limit: int = 50) -> list[SearchHit]:
        q = (query or "").strip()
        if len(q) < 1:
            return []
        pat = _sql_like_pattern(q)
        lim = max(1, min(int(limit), 200))
        hits: list[SearchHit] = []

        for r in self.conn.execute(
            """
            SELECT id, name FROM customers
            WHERE is_deleted = 0 AND name LIKE ? ESCAPE '\\'
            ORDER BY name
            LIMIT ?
            """,
            (pat, lim),
        ).fetchall():
            hits.append(
                SearchHit(
                    kind="customer",
                    record_id=int(r["id"]),
                    title=str(r["name"]),
                    detail="Customer",
                    customer_id=int(r["id"]),
                )
            )

        for r in self.conn.execute(
            """
            SELECT i.id, i.invoice_no, i.excel_path, c.name AS customer_name, i.customer_id
            FROM invoices i
            JOIN customers c ON c.id = i.customer_id
            WHERE i.is_deleted = 0
              AND (i.invoice_no LIKE ? ESCAPE '\\' OR c.name LIKE ? ESCAPE '\\')
            ORDER BY i.invoice_date DESC, i.invoice_no DESC
            LIMIT ?
            """,
            (pat, pat, lim),
        ).fetchall():
            xp = r["excel_path"]
            hits.append(
                SearchHit(
                    kind="invoice",
                    record_id=int(r["id"]),
                    title=str(r["invoice_no"]),
                    detail=str(r["customer_name"]),
                    customer_id=int(r["customer_id"]),
                    invoice_id=int(r["id"]),
                    excel_path=str(xp).strip() if xp else None,
                )
            )

        for r in self.conn.execute(
            """
            SELECT p.id, p.amount, p.payment_date, p.reference, c.name AS customer_name, p.customer_id
            FROM payments p
            JOIN customers c ON c.id = p.customer_id
            WHERE p.is_deleted = 0
              AND (
                p.reference LIKE ? ESCAPE '\\'
                OR p.notes LIKE ? ESCAPE '\\'
                OR p.mode LIKE ? ESCAPE '\\'
                OR c.name LIKE ? ESCAPE '\\'
                OR CAST(p.amount AS TEXT) LIKE ? ESCAPE '\\'
              )
            ORDER BY p.payment_date DESC, p.id DESC
            LIMIT ?
            """,
            (pat, pat, pat, pat, pat, lim),
        ).fetchall():
            hits.append(
                SearchHit(
                    kind="payment",
                    record_id=int(r["id"]),
                    title=f"{float(r['amount']):,.2f} on {_d(r['payment_date']).strftime('%d-%m-%Y')}",
                    detail=f"{r['customer_name']} · {r['reference'] or '—'}",
                    customer_id=int(r["customer_id"]),
                )
            )

        for r in self.conn.execute(
            """
            SELECT id, name, hsn, unit
            FROM items
            WHERE is_deleted = 0 AND name LIKE ? ESCAPE '\\'
            ORDER BY name
            LIMIT ?
            """,
            (pat, lim),
        ).fetchall():
            hsn = r["hsn"] or ""
            unit = r["unit"] or ""
            hits.append(
                SearchHit(
                    kind="item",
                    record_id=int(r["id"]),
                    title=str(r["name"]),
                    detail=f"Product  ·  HSN {hsn or '—'}  ·  {unit or '—'}",
                )
            )

        for r in self.conn.execute(
            """
            SELECT id, short_code, unit
            FROM raw_materials
            WHERE is_deleted = 0 AND short_code LIKE ? ESCAPE '\\'
            ORDER BY short_code
            LIMIT ?
            """,
            (pat, lim),
        ).fetchall():
            unit = r["unit"] or ""
            hits.append(
                SearchHit(
                    kind="raw_material",
                    record_id=int(r["id"]),
                    title=str(r["short_code"]),
                    detail=f"Raw material  ·  {unit or '—'}",
                    raw_material_id=int(r["id"]),
                )
            )

        for r in self.conn.execute(
            """
            SELECT l.id, l.lot_code, l.supplier_ref, l.notes, r.short_code AS rm_code, r.id AS raw_material_id
            FROM rm_stock_lots l
            JOIN raw_materials r ON r.id = l.raw_material_id AND r.is_deleted = 0
            WHERE l.lot_code LIKE ? ESCAPE '\\'
               OR IFNULL(l.supplier_ref, '') LIKE ? ESCAPE '\\'
               OR IFNULL(l.notes, '') LIKE ? ESCAPE '\\'
            ORDER BY l.created_at DESC, l.id DESC
            LIMIT ?
            """,
            (pat, pat, pat, lim),
        ).fetchall():
            sr = r["supplier_ref"] or ""
            nt = (r["notes"] or "").strip()
            hits.append(
                SearchHit(
                    kind="rm_lot",
                    record_id=int(r["id"]),
                    title=str(r["lot_code"]),
                    detail=f"RM {r['rm_code']}  ·  {sr or '—'}"
                    + (f"  ·  {nt[:80]}{'…' if len(nt) > 80 else ''}" if nt else ""),
                    raw_material_id=int(r["raw_material_id"]),
                )
            )

        return hits[:lim]

    # ---- payments list (for UI) ----
    def list_payments_recent(self, limit: int = 80) -> list[sqlite3.Row]:
        lim = max(1, min(int(limit), 500))
        return list(
            self.conn.execute(
                """
                SELECT p.id, p.customer_id, p.payment_date, p.amount, p.mode, p.reference, c.name AS customer_name
                FROM payments p
                JOIN customers c ON c.id = p.customer_id
                WHERE p.is_deleted = 0
                ORDER BY p.payment_date DESC, p.id DESC
                LIMIT ?
                """,
                (lim,),
            ).fetchall()
        )

    def get_invoice_excel_path(self, invoice_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT excel_path FROM invoices WHERE id = ? AND is_deleted = 0", (invoice_id,)
        ).fetchone()
        if row is None:
            return None
        xp = row["excel_path"]
        return str(xp).strip() if xp else None

    def get_invoice_no(self, invoice_id: int) -> str | None:
        row = self.conn.execute(
            "SELECT invoice_no FROM invoices WHERE id = ? AND is_deleted = 0", (invoice_id,)
        ).fetchone()
        if row is None:
            return None
        return str(row["invoice_no"] or "").strip() or None

    def permanently_delete_invoice(self, invoice_id: int) -> None:
        """
        Hard-delete invoice row (not soft delete / not in Trash). Cascades remove
        invoice_items and allocations for this invoice.
        """
        row = self.conn.execute(
            """
            SELECT invoice_no, total_after_tax, customer_id
            FROM invoices WHERE id = ? AND is_deleted = 0
            """,
            (invoice_id,),
        ).fetchone()
        n = self.conn.execute(
            "DELETE FROM invoices WHERE id = ? AND is_deleted = 0", (invoice_id,)
        ).rowcount
        if n == 0:
            raise ValueError("Invoice not found or already in trash — use Restore or Trash flow.")
        if row is not None:
            cnm = self.conn.execute(
                "SELECT name FROM customers WHERE id = ?", (int(row["customer_id"]),)
            ).fetchone()
            cname = str(cnm["name"]) if cnm else ""
            self.audit_log_append(
                action="invoice_deleted_permanent",
                entity_type="invoice",
                entity_id=invoice_id,
                detail=(
                    f"invoice_no={row['invoice_no']}; customer={cname}; "
                    f"total={float(row['total_after_tax']):.2f}"
                ),
            )

    # ---- soft delete / restore ----
    def soft_delete_customer(self, customer_id: int) -> None:
        self.conn.execute(
            """
            UPDATE customers
            SET is_deleted = 1, deleted_at = datetime('now'), updated_at = datetime('now')
            WHERE id = ? AND is_deleted = 0
            """,
            (customer_id,),
        )

    def restore_customer(self, customer_id: int) -> None:
        self.conn.execute(
            """
            UPDATE customers
            SET is_deleted = 0, deleted_at = NULL, updated_at = datetime('now')
            WHERE id = ? AND is_deleted = 1
            """,
            (customer_id,),
        )

    def soft_delete_invoice(self, invoice_id: int) -> None:
        row = self.conn.execute(
            """
            SELECT invoice_no, total_after_tax, customer_id
            FROM invoices WHERE id = ? AND is_deleted = 0
            """,
            (invoice_id,),
        ).fetchone()
        cur = self.conn.execute(
            """
            UPDATE invoices
            SET is_deleted = 1, deleted_at = datetime('now'), updated_at = datetime('now')
            WHERE id = ? AND is_deleted = 0
            """,
            (invoice_id,),
        )
        if row is not None and cur.rowcount:
            cnm = self.conn.execute(
                "SELECT name FROM customers WHERE id = ?", (int(row["customer_id"]),)
            ).fetchone()
            cname = str(cnm["name"]) if cnm else ""
            self.audit_log_append(
                action="invoice_trashed",
                entity_type="invoice",
                entity_id=invoice_id,
                detail=(
                    f"invoice_no={row['invoice_no']}; customer={cname}; "
                    f"total={float(row['total_after_tax']):.2f}"
                ),
            )

    def restore_invoice(self, invoice_id: int) -> None:
        row = self.conn.execute(
            "SELECT invoice_no FROM invoices WHERE id = ? AND is_deleted = 1",
            (invoice_id,),
        ).fetchone()
        cur = self.conn.execute(
            """
            UPDATE invoices
            SET is_deleted = 0, deleted_at = NULL, updated_at = datetime('now')
            WHERE id = ? AND is_deleted = 1
            """,
            (invoice_id,),
        )
        if row is not None and cur.rowcount:
            self.audit_log_append(
                action="invoice_restored",
                entity_type="invoice",
                entity_id=invoice_id,
                detail=f"invoice_no={row['invoice_no']}",
            )

    def soft_delete_payment(self, payment_id: int) -> None:
        row = self.conn.execute(
            """
            SELECT amount, customer_id, reference
            FROM payments WHERE id = ? AND is_deleted = 0
            """,
            (payment_id,),
        ).fetchone()
        cur = self.conn.execute(
            """
            UPDATE payments
            SET is_deleted = 1, deleted_at = datetime('now'), updated_at = datetime('now')
            WHERE id = ? AND is_deleted = 0
            """,
            (payment_id,),
        )
        if row is not None and cur.rowcount:
            cnm = self.conn.execute(
                "SELECT name FROM customers WHERE id = ?", (int(row["customer_id"]),)
            ).fetchone()
            cname = str(cnm["name"]) if cnm else ""
            ref_s = str(row["reference"] or "").strip()
            self.audit_log_append(
                action="payment_trashed",
                entity_type="payment",
                entity_id=payment_id,
                detail=(
                    f"customer={cname}; amount={float(row['amount']):.2f}"
                    + (f"; ref={ref_s}" if ref_s else "")
                ),
            )

    def restore_payment(self, payment_id: int) -> None:
        row = self.conn.execute(
            "SELECT amount FROM payments WHERE id = ? AND is_deleted = 1",
            (payment_id,),
        ).fetchone()
        cur = self.conn.execute(
            """
            UPDATE payments
            SET is_deleted = 0, deleted_at = NULL, updated_at = datetime('now')
            WHERE id = ? AND is_deleted = 1
            """,
            (payment_id,),
        )
        if row is not None and cur.rowcount:
            self.audit_log_append(
                action="payment_restored",
                entity_type="payment",
                entity_id=payment_id,
                detail=f"amount={float(row['amount']):.2f}",
            )

    def soft_delete_item(self, item_id: int) -> None:
        self.conn.execute(
            """
            UPDATE items
            SET is_deleted = 1, deleted_at = datetime('now'), updated_at = datetime('now')
            WHERE id = ? AND is_deleted = 0
            """,
            (item_id,),
        )

    def restore_item(self, item_id: int) -> None:
        self.conn.execute(
            """
            UPDATE items
            SET is_deleted = 0, deleted_at = NULL, updated_at = datetime('now')
            WHERE id = ? AND is_deleted = 1
            """,
            (item_id,),
        )

    def list_deleted_customers(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT id, name, deleted_at
                FROM customers
                WHERE is_deleted = 1
                ORDER BY deleted_at DESC, name
                """
            ).fetchall()
        )

    def list_deleted_invoices(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT i.id, i.invoice_no, i.invoice_date, i.total_after_tax, c.name AS customer_name, i.deleted_at
                FROM invoices i
                LEFT JOIN customers c ON c.id = i.customer_id
                WHERE i.is_deleted = 1
                ORDER BY i.deleted_at DESC, i.invoice_no DESC
                """
            ).fetchall()
        )

    def list_deleted_payments(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT p.id, p.payment_date, p.amount, p.reference, c.name AS customer_name, p.deleted_at
                FROM payments p
                LEFT JOIN customers c ON c.id = p.customer_id
                WHERE p.is_deleted = 1
                ORDER BY p.deleted_at DESC, p.id DESC
                """
            ).fetchall()
        )

    def list_deleted_items(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                """
                SELECT id, name, hsn, deleted_at
                FROM items
                WHERE is_deleted = 1
                ORDER BY deleted_at DESC, name
                """
            ).fetchall()
        )

