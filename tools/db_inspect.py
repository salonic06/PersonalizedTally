from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.paths import get_paths


def main() -> int:
    db = get_paths().db_path
    print("db_path:", db)
    print("exists:", db.exists())
    if not db.exists():
        return 1

    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    row = cur.execute(
        """
        SELECT
          COUNT(*) AS n,
          SUM(CASE WHEN gstin IS NULL OR trim(gstin)='' THEN 1 ELSE 0 END) AS gst_blank,
          SUM(CASE WHEN state IS NULL OR trim(state)='' THEN 1 ELSE 0 END) AS state_blank,
          SUM(CASE WHEN state_code IS NULL OR trim(state_code)='' THEN 1 ELSE 0 END) AS code_blank,
          SUM(CASE WHEN address IS NULL OR trim(address)='' THEN 1 ELSE 0 END) AS addr_blank
        FROM customers
        WHERE is_deleted=0
        """
    ).fetchone()
    print("customers_blank_summary:", dict(row))

    rows = cur.execute(
        """
        SELECT id,name,gstin,state,state_code,address
        FROM customers
        WHERE is_deleted=0 AND (
          gstin IS NULL OR trim(gstin)='' OR
          state IS NULL OR trim(state)='' OR
          state_code IS NULL OR trim(state_code)='' OR
          address IS NULL OR trim(address)=''
        )
        ORDER BY name
        LIMIT 10
        """
    ).fetchall()
    print("sample_customers_with_blanks:")
    for r in rows:
        print(
            r["id"],
            r["name"],
            "gst=",
            bool(r["gstin"]),
            "state=",
            bool(r["state"]),
            "code=",
            bool(r["state_code"]),
            "addr=",
            bool(r["address"]),
        )

    fy_start = "2026-04-01"
    fy_end = "2027-03-31"
    inv_rows = cur.execute(
        """
        SELECT invoice_no, invoice_date
        FROM invoices
        WHERE is_deleted=0 AND invoice_date>=? AND invoice_date<=?
        ORDER BY invoice_date, invoice_no
        """,
        (fy_start, fy_end),
    ).fetchall()
    print("invoices_FY_2026_2027_count:", len(inv_rows))

    mx = 0
    for r in inv_rows:
        s = str(r["invoice_no"] or "").strip()
        if s.isdigit():
            mx = max(mx, int(s))
    print("max_numeric_invoice_no_FY_2026_2027:", mx)
    print("first_10_invoices_FY_2026_2027:")
    for r in inv_rows[:10]:
        print(r["invoice_date"], r["invoice_no"])

    con.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

