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


def _login(client: TestClient, username: str = "owner", password: str = "owner123") -> None:
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text


def test_api_requires_auth(api_client: TestClient) -> None:
    assert api_client.get("/api/dashboard").status_code == 401
    assert api_client.get("/api/health").status_code == 200


def test_api_login_and_dashboard(api_client: TestClient) -> None:
    _login(api_client)
    me = api_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "owner"

    d = api_client.get("/api/dashboard")
    assert d.status_code == 200
    body = d.json()
    assert body["total_outstanding"] >= 1000.0


def test_api_create_payment_fifo(api_client: TestClient) -> None:
    _login(api_client)
    repo: Repo = api_client.app.state.repo
    cid = int(repo.list_customers()[0]["id"])
    before = repo.dashboard_summary(date.today()).total_outstanding

    r = api_client.post(
        "/api/payments",
        json={
            "customer_id": cid,
            "payment_date": date.today().isoformat(),
            "amount": 100.0,
            "mode": "UPI",
            "reference": "TEST-UTR",
        },
    )
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert pid > 0

    after = repo.dashboard_summary(date.today()).total_outstanding
    assert after <= before - 99.0

    recent = api_client.get("/api/payments?limit=5")
    assert any(p["id"] == pid for p in recent.json())


def test_api_worker_can_pay_owner_can_add_customer(api_client: TestClient) -> None:
    _login(api_client, "worker", "worker123")
    repo: Repo = api_client.app.state.repo
    cid = int(repo.list_customers()[0]["id"])
    assert (
        api_client.post(
            "/api/payments",
            json={
                "customer_id": cid,
                "payment_date": date.today().isoformat(),
                "amount": 50.0,
                "mode": "Cash",
            },
        ).status_code
        == 201
    )
    assert api_client.post("/api/customers", json={"name": "Worker Blocked", "credit_days": 30}).status_code == 403

    _login(api_client)
    r = api_client.post("/api/customers", json={"name": "Web New Co", "credit_days": 45})
    assert r.status_code == 201
    assert r.json()["name"] == "Web New Co"


def test_api_due_overdue_filter(api_client: TestClient) -> None:
    _login(api_client)
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
