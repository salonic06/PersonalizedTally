from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.db.conn import connect
from src.db.migrate import migrate
from src.repo import Repo


def _repo(tmp_path: Path) -> Repo:
    conn = connect(tmp_path / "fifo_cogs.db")
    migrate(conn)
    return Repo(conn)


def _invoice_outstanding(repo: Repo, invoice_id: int) -> float:
    row = repo.conn.execute(
        "SELECT outstanding FROM invoice_balances WHERE invoice_id = ?",
        (invoice_id,),
    ).fetchone()
    assert row is not None
    return float(row["outstanding"])


def _allocations(repo: Repo, payment_id: int) -> list[tuple[int, float]]:
    rows = repo.conn.execute(
        """
        SELECT invoice_id, amount FROM allocations
        WHERE payment_id = ?
        ORDER BY invoice_id ASC
        """,
        (payment_id,),
    ).fetchall()
    return [(int(r["invoice_id"]), float(r["amount"])) for r in rows]


def test_allocate_payment_fifo_oldest_due_first(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    cid = repo.upsert_customer("FIFO PayCo", 30)
    inv_a = repo.create_invoice(cid, "A-001", date(2026, 1, 1), 1000.0, None)
    inv_b = repo.create_invoice(cid, "B-002", date(2026, 2, 1), 2000.0, None)
    inv_c = repo.create_invoice(cid, "C-003", date(2026, 3, 1), 3000.0, None)

    # Force due-date ordering independent of credit_days defaults.
    repo.conn.execute(
        "UPDATE invoices SET due_date = ? WHERE id = ?",
        ("2026-04-01", inv_a),
    )
    repo.conn.execute(
        "UPDATE invoices SET due_date = ? WHERE id = ?",
        ("2026-04-15", inv_b),
    )
    repo.conn.execute(
        "UPDATE invoices SET due_date = ? WHERE id = ?",
        ("2026-05-01", inv_c),
    )
    repo.conn.commit()

    pay_id = repo.create_payment(cid, date(2026, 5, 10), 2500.0)
    allocs = dict(_allocations(repo, pay_id))

    assert allocs[inv_a] == pytest.approx(1000.0)
    assert allocs[inv_b] == pytest.approx(1500.0)
    assert inv_c not in allocs

    assert _invoice_outstanding(repo, inv_a) == pytest.approx(0.0)
    assert _invoice_outstanding(repo, inv_b) == pytest.approx(500.0)
    assert _invoice_outstanding(repo, inv_c) == pytest.approx(3000.0)


def test_allocate_payment_fifo_partial_oldest_invoice(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    cid = repo.upsert_customer("Partial Co", 30)
    inv_old = repo.create_invoice(cid, "OLD-1", date(2026, 4, 1), 500.0, None)
    inv_new = repo.create_invoice(cid, "NEW-2", date(2026, 4, 2), 800.0, None)
    repo.conn.execute(
        "UPDATE invoices SET due_date = ? WHERE id = ?",
        ("2026-04-10", inv_old),
    )
    repo.conn.execute(
        "UPDATE invoices SET due_date = ? WHERE id = ?",
        ("2026-04-20", inv_new),
    )
    repo.conn.commit()

    pay_id = repo.create_payment(cid, date(2026, 4, 15), 200.0)
    allocs = dict(_allocations(repo, pay_id))

    assert allocs == {inv_old: pytest.approx(200.0)}
    assert _invoice_outstanding(repo, inv_old) == pytest.approx(300.0)
    assert _invoice_outstanding(repo, inv_new) == pytest.approx(800.0)


def test_add_batch_consumption_fifo_uses_oldest_lots_first(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    pid = repo.upsert_item("Widget", default_rate=10.0)
    rm_id = repo.add_raw_material("Resin", "RSN", unit="Kg")
    repo.receive_rm_stock_lot(rm_id, date(2026, 3, 1), 100.0, 10.0)
    repo.receive_rm_stock_lot(rm_id, date(2026, 4, 1), 100.0, 20.0)
    batch_id, _ = repo.create_production_batch("01", pid, date(2026, 4, 10))

    repo.add_batch_consumption_fifo(batch_id, rm_id, 120.0)

    lots = repo.conn.execute(
        """
        SELECT l.lot_code, l.qty_remaining, c.qty_consumed, c.source
        FROM batch_rm_consumption c
        JOIN rm_stock_lots l ON l.id = c.rm_stock_lot_id
        WHERE c.batch_id = ?
        ORDER BY l.received_date ASC
        """,
        (batch_id,),
    ).fetchall()
    assert len(lots) == 2
    assert float(lots[0]["qty_consumed"]) == pytest.approx(100.0)
    assert float(lots[0]["qty_remaining"]) == pytest.approx(0.0)
    assert str(lots[0]["source"]) == "fifo"
    assert float(lots[1]["qty_consumed"]) == pytest.approx(20.0)
    assert float(lots[1]["qty_remaining"]) == pytest.approx(80.0)
    assert repo.batch_rm_material_cost(batch_id) == pytest.approx(100.0 * 10.0 + 20.0 * 20.0)


def test_production_batch_cost_per_kg_and_invoice_line_cogs(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    pid = repo.upsert_item("Panel", default_rate=100.0)
    rm_id = repo.add_raw_material("Core", "COR", unit="Kg")
    repo.receive_rm_stock_lot(rm_id, date(2026, 4, 1), 50.0, 100.0)
    batch_id, _ = repo.create_production_batch("B1", pid, date(2026, 4, 5))
    repo.add_batch_consumption_fifo(batch_id, rm_id, 50.0)
    repo.update_production_batch_costing(
        batch_id, batch_yield_kg=100.0, conversion_cost_per_kg=10.0
    )

    # RM 5000 / 100 kg yield + 10 conversion = 60 ₹/kg
    assert repo.batch_rm_material_cost(batch_id) == pytest.approx(5000.0)
    assert repo.production_batch_cost_per_kg(batch_id) == pytest.approx(60.0)
    assert repo.invoice_line_cogs_amount(25.0, batch_id) == pytest.approx(1500.0)


def test_list_invoice_gross_profits_with_batch_cogs(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    cid = repo.upsert_customer("Margin Co", 30)
    pid = repo.upsert_item("Sheet", default_rate=200.0)
    repo.add_raw_material("FG Sheet", "FGS", product_item_id=pid)
    rm_in = repo.add_raw_material("Input", "INP", unit="Kg")
    repo.receive_rm_stock_lot(rm_in, date(2026, 4, 1), 10.0, 50.0)
    batch_id, _ = repo.create_production_batch("M2", pid, date(2026, 4, 2))
    repo.add_batch_consumption_fifo(batch_id, rm_in, 10.0)
    repo.update_production_batch_costing(
        batch_id, batch_yield_kg=10.0, conversion_cost_per_kg=0.0
    )
    # cost/kg = 500 / 10 = 50

    inv_id = repo.create_invoice(cid, "INV-GP", date(2026, 4, 10), 1180.0, None)
    repo.add_invoice_items(
        inv_id,
        [
            {
                "line_no": 1,
                "description": "Sheet",
                "qty": 4.0,
                "rate": 100.0,
                "amount": 400.0,
                "production_batch_id": batch_id,
                "product_item_id": pid,
            },
        ],
    )

    profits = {p.invoice_id: p for p in repo.list_invoice_gross_profits()}
    row = profits[inv_id]
    assert row.revenue_ex_gst == pytest.approx(400.0)
    assert row.cogs == pytest.approx(200.0)  # 4 kg * 50 ₹/kg
    assert row.gross_profit == pytest.approx(200.0)
    assert row.lines_with_cogs == 1
    assert row.cogs_complete is True

    fg_rem = repo.finished_good_qty_remaining_for_batch(batch_id)
    assert fg_rem is not None
    assert fg_rem == pytest.approx(6.0)  # 10 yield - 4 sold
