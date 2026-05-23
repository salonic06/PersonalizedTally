"""
Reset the local SQLite DB and load demo customers, invoices, payments, RM stock,
and one production batch — useful for screenshots and feature walkthroughs.

Usage (from repo root, with venv activated):

  python tools/seed_demo.py --yes

This deletes data/personalized_tally.db (and lamitech.db / WAL sidecars) then rebuilds.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db.conn import connect  # noqa: E402
from src.db.migrate import migrate  # noqa: E402
from src.paths import get_paths  # noqa: E402
from src.repo import Repo  # noqa: E402


def _wipe_local_database_files(data_dir: Path) -> None:
    names = ("personalized_tally.db", "lamitech.db")
    for base in names:
        p = data_dir / base
        if p.exists():
            p.unlink()
        for suf in ("-wal", "-shm"):
            side = Path(str(p) + suf)
            if side.exists():
                side.unlink()


def _line(line_no: int, desc: str, hsn: str, qty: float, unit: str, rate: float) -> dict:
    amt = round(float(qty) * float(rate), 2)
    return {
        "line_no": line_no,
        "description": desc,
        "hsn": hsn,
        "qty": qty,
        "unit": unit,
        "rate": rate,
        "amount": amt,
    }


def _gst_total(taxable: float) -> float:
    return round(float(taxable) * 1.18, 2)


def seed_demo(repo: Repo, *, root: Path, anchor: date) -> None:
    fy = anchor.year if anchor.month >= 4 else anchor.year - 1
    out_dir = root / "invoices" / f"{fy}-{fy + 1}"
    out_dir.mkdir(parents=True, exist_ok=True)
    tpl = root / "assets" / "invoice_template.xlsx"

    repo.set_setting("default_credit_days", "45")
    repo.set_setting("invoice_template_path", str(tpl))
    repo.set_setting("invoice_output_folder", str(out_dir))

    # --- masters ---
    upsert = repo.upsert_customer
    g = upsert("Gamma Industries Ltd", 30)
    d = upsert("Delta Polymers Pvt Ltd", 45)
    e = upsert("Epsilon Trading Co", 15)
    z = upsert("Zeta Packaging Solutions", 60)

    repo.update_customer_details(
        g,
        name="Gamma Industries Ltd",
        credit_days=30,
        gstin="27AAAAA0000A1Z5",
        state="Maharashtra",
        state_code="27",
        address="MIDC Phase 2, Pune",
    )

    pid_a = repo.upsert_item("FinishGrade-A", "3907", "Kg", 118.0)
    repo.upsert_item("FinishGrade-B", "3907", "Kg", 96.0)
    repo.upsert_item("Bulk additive pack", "3824", "Nos", 420.0)

    rm_ep = repo.add_raw_material(
        "Epoxy resin base",
        "EPXY",
        unit="Kg",
        material_type="Resin",
        reorder_level=280.0,
    )
    rm_hd = repo.add_raw_material(
        "Hardener concentrate",
        "HRDN",
        unit="Kg",
        material_type="Hardener",
        reorder_level=180.0,
    )

    repo.receive_rm_stock_lot(rm_ep, anchor - timedelta(days=48), 320.0, 210.5, supplier_ref="PO-7711")
    repo.receive_rm_stock_lot(rm_ep, anchor - timedelta(days=4), 55.0, 215.0, supplier_ref="PO-9022")
    repo.receive_rm_stock_lot(rm_hd, anchor - timedelta(days=11), 140.0, 92.0, supplier_ref="GRN-H12")

    bid, bcode = repo.create_production_batch(
        "DEMO01",
        pid_a,
        anchor - timedelta(days=16),
        notes="Demo batch for portfolio / training walkthrough.",
    )
    repo.add_batch_consumption_fifo(bid, rm_ep, 58.0)
    repo.update_production_batch_costing(
        bid,
        batch_yield_kg=48.0,
        conversion_cost_per_kg=14.25,
    )

    demo_desc = "Industrial coating blend — demo line"
    # Gamma: spread due dates for aging buckets + FIFO payment demo
    specs_g = [
        ("G-DEMO-001", anchor - timedelta(days=150), 10_000.00),
        ("G-DEMO-002", anchor - timedelta(days=75), 20_000.00),
        ("G-DEMO-003", anchor - timedelta(days=36), 15_000.00),
        ("G-DEMO-004", anchor - timedelta(days=5), 25_000.00),
    ]
    for no, inv_dt, taxable in specs_g:
        tot = _gst_total(taxable)
        iid = repo.create_invoice(g, no, inv_dt, tot, excel_path=None)
        repo.add_invoice_items(iid, [_line(1, demo_desc, "3907", 100.0, "Kg", taxable / 100.0)])

    specs_d = [("D-DEMO-101", anchor - timedelta(days=73), 60_000.00)]
    for no, inv_dt, taxable in specs_d:
        tot = _gst_total(taxable)
        iid = repo.create_invoice(d, no, inv_dt, tot, excel_path=None)
        repo.add_invoice_items(iid, [_line(1, demo_desc, "3907", 240.0, "Kg", taxable / 240.0)])

    specs_e = [("E-DEMO-201", anchor - timedelta(days=67), 30_000.00)]
    for no, inv_dt, taxable in specs_e:
        tot = _gst_total(taxable)
        iid = repo.create_invoice(e, no, inv_dt, tot, excel_path=None)
        repo.add_invoice_items(iid, [_line(1, demo_desc, "3907", 120.0, "Kg", taxable / 120.0)])

    specs_z = [("Z-DEMO-301", anchor - timedelta(days=64), 4_000.00)]
    for no, inv_dt, taxable in specs_z:
        tot = _gst_total(taxable)
        iid = repo.create_invoice(z, no, inv_dt, tot, excel_path=None)
        repo.add_invoice_items(iid, [_line(1, "Annual freight surcharge allocation", "9965", 1.0, "Job", taxable)])

    # Payment clears oldest Gamma invoices first (FIFO), partially touches third
    repo.create_payment(
        g,
        anchor - timedelta(days=10),
        40_000.0,
        mode="NEFT",
        reference="UTR-DEMO-884422",
        notes="Demo receipt against oldest Gamma invoices",
    )

    repo.create_payment(
        d,
        anchor - timedelta(days=3),
        15_000.0,
        mode="Cheque",
        reference="CHQ-112233",
        notes="Partial on Delta — demo",
    )

    # Balances due today (invoice_date + credit_days → due_date == anchor) for Reminders walkthrough
    due_today_specs = [
        (d, "D-DUE-TODAY-1", 45, 18_000.00),
        (e, "E-DUE-TODAY-2", 15, 9_500.00),
    ]
    for cust_id, inv_no, credit_days, taxable in due_today_specs:
        inv_dt = anchor - timedelta(days=credit_days)
        tot = _gst_total(taxable)
        iid = repo.create_invoice(cust_id, inv_no, inv_dt, tot, excel_path=None)
        repo.add_invoice_items(
            iid,
            [_line(1, demo_desc, "3907", 50.0, "Kg", taxable / 50.0)],
        )

    repo.audit_log_append(
        action="demo_seed_completed",
        entity_type="system",
        entity_id=None,
        detail=f"Loaded demo dataset; anchor_date={anchor.isoformat()}; batch={bcode}",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Wipe DB and load Personalized Tally demo data.")
    ap.add_argument(
        "--yes",
        action="store_true",
        help="Confirm destructive wipe of local database files under data/",
    )
    args = ap.parse_args()
    if not args.yes:
        print("Refusing to wipe database without --yes. Run: python tools/seed_demo.py --yes")
        return 2

    paths = get_paths()
    data_dir = paths.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    _wipe_local_database_files(data_dir)

    conn = connect(paths.db_path)
    # Avoid nested BEGIN when repo helpers use `transaction(conn)` (Python sqlite3 defaults otherwise).
    conn.isolation_level = None
    migrate(conn)
    repo = Repo(conn)
    anchor = date.today()
    try:
        seed_demo(repo, root=paths.root, anchor=anchor)
    finally:
        conn.close()

    print(f"Demo database ready at {paths.db_path}")
    print(f"Demo anchor date (invoice aging vs today): {anchor.isoformat()}")
    print("Open the app with: python app.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
