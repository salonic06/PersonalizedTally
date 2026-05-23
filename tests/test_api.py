from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.main import app
from src.paths import AppPaths
from src.repo import Repo


@pytest.fixture
def api_client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    db_path = data_dir / "personalized_tally.db"
    paths = AppPaths(root=tmp_path, data_dir=data_dir, db_path=db_path)
    monkeypatch.setattr("api.main.get_paths", lambda: paths)

    with TestClient(app) as client:
        repo: Repo = client.app.state.repo
        cid = repo.upsert_customer("API Co", 30)
        repo.create_invoice(cid, "API-1", date(2026, 5, 1), 1000.0, None)
        yield client


def test_api_health_and_dashboard(api_client: TestClient) -> None:
    r = api_client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    d = api_client.get("/api/dashboard")
    assert d.status_code == 200
    body = d.json()
    assert body["total_outstanding"] >= 1000.0
    assert "as_of" in body


def test_api_due_overdue_filter(api_client: TestClient) -> None:
    repo: Repo = api_client.app.state.repo
    rows = repo.conn.execute("SELECT customer_id FROM invoices LIMIT 1").fetchone()
    cid = int(rows["customer_id"])
    inv_id = repo.create_invoice(cid, "OLD", date(2026, 1, 1), 500.0, None)
    repo.conn.execute(
        "UPDATE invoices SET due_date = ? WHERE id = ?",
        ("2026-04-01", inv_id),
    )
    repo.conn.commit()

    due_rows = api_client.get("/api/due?overdue=true").json()
    assert any(x["invoice_no"] == "OLD" for x in due_rows)
