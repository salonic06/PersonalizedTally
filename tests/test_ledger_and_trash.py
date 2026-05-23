from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.db.conn import connect
from src.db.migrate import migrate
from src.repo import Repo


def _repo(tmp_path: Path) -> Repo:
    conn = connect(tmp_path / "ledger.db")
    migrate(conn)
    return Repo(conn)


def test_ledger_running_balance_invoice_then_payment(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    cid = repo.upsert_customer("Ledger Co", 30)
    repo.create_invoice(cid, "INV-1", date(2026, 5, 1), 1180.0, None)
    repo.create_payment(cid, date(2026, 5, 15), 400.0, reference="UTR-1")

    rows = repo.ledger_rows(cid)
    assert len(rows) == 2
    assert rows[0].entry_type == "INVOICE"
    assert rows[0].debit == pytest.approx(1180.0)
    assert rows[0].balance == pytest.approx(1180.0)
    assert rows[1].entry_type == "PAYMENT"
    assert rows[1].credit == pytest.approx(400.0)
    assert rows[1].balance == pytest.approx(780.0)


def test_ledger_net_before_excludes_same_day_movements(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    cid = repo.upsert_customer("Net Co", 30)
    repo.create_invoice(cid, "A", date(2026, 5, 1), 1000.0, None)
    repo.create_invoice(cid, "B", date(2026, 5, 10), 500.0, None)
    assert repo.ledger_net_before(cid, date(2026, 5, 10)) == pytest.approx(1000.0)
    assert repo.ledger_net_before(cid, date(2026, 5, 11)) == pytest.approx(1500.0)


def test_trashed_payment_removed_from_ledger_and_restored(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    cid = repo.upsert_customer("Trash Ledger", 30)
    inv_id = repo.create_invoice(cid, "T-1", date(2026, 5, 1), 1000.0, None)
    pay_id = repo.create_payment(cid, date(2026, 5, 5), 300.0)

    assert len(repo.ledger_rows(cid)) == 2
    bal = repo.conn.execute(
        "SELECT outstanding FROM invoice_balances WHERE invoice_id = ?",
        (inv_id,),
    ).fetchone()
    assert float(bal["outstanding"]) == pytest.approx(700.0)

    repo.soft_delete_payment(pay_id)
    assert len(repo.ledger_rows(cid)) == 1
    bal2 = repo.conn.execute(
        "SELECT outstanding FROM invoice_balances WHERE invoice_id = ?",
        (inv_id,),
    ).fetchone()
    assert float(bal2["outstanding"]) == pytest.approx(1000.0)

    deleted = repo.list_deleted_payments()
    assert any(int(r["id"]) == pay_id for r in deleted)

    repo.restore_payment(pay_id)
    assert len(repo.ledger_rows(cid)) == 2
    rows = repo.ledger_rows(cid)
    assert rows[-1].credit == pytest.approx(300.0)
    assert rows[-1].balance == pytest.approx(700.0)


def test_trashed_payment_clears_allocations_from_active_balance(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    cid = repo.upsert_customer("Alloc Trash", 30)
    inv_id = repo.create_invoice(cid, "AT-1", date(2026, 5, 1), 1000.0, None)
    pay_id = repo.create_payment(cid, date(2026, 5, 2), 1000.0)

    assert repo.conn.execute(
        "SELECT outstanding FROM invoice_balances WHERE invoice_id = ?",
        (inv_id,),
    ).fetchone()["outstanding"] == pytest.approx(0.0)

    repo.soft_delete_payment(pay_id)
    assert repo.conn.execute(
        "SELECT outstanding FROM invoice_balances WHERE invoice_id = ?",
        (inv_id,),
    ).fetchone()["outstanding"] == pytest.approx(1000.0)

    alloc_rows = repo.conn.execute(
        "SELECT COUNT(*) AS c FROM allocations a "
        "JOIN payments p ON p.id = a.payment_id WHERE p.is_deleted = 0 AND a.invoice_id = ?",
        (inv_id,),
    ).fetchone()
    assert int(alloc_rows["c"]) == 0
