from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from src.db.conn import connect
from src.db.migrate import migrate
from src.notifications import collect_notifications
from src.owner_digest import build_owner_digest
from src.paths import get_paths

from .auth import OwnerDep, UserDep, clear_session, set_session, web_secret
from .cors import cors_settings
from .deps import RepoDep
from .schemas import (
    CustomerCreateIn,
    CustomerOut,
    DashboardOut,
    DueRowOut,
    HealthOut,
    LoginIn,
    PaymentCreateIn,
    PaymentCreatedOut,
    PaymentOut,
    ReminderOut,
    RemindersOut,
    UserOut,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    paths = get_paths()
    conn = connect(paths.db_path, check_same_thread=False)
    migrate(conn)
    from src.repo import Repo

    app.state.conn = conn
    app.state.repo = Repo(conn)
    app.state.db_path = str(paths.db_path)
    yield
    conn.close()


app = FastAPI(
    title="Personalized Tally API",
    description=(
        "HTTP API over the desktop app's SQLite database. "
        "Sign in with owner/worker credentials; record payments with the same FIFO rules as PySide6."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, **cors_settings())
app.add_middleware(SessionMiddleware, secret_key=web_secret(), same_site="lax", https_only=False)


@app.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut()


@app.post("/api/auth/login", response_model=UserOut)
def login(body: LoginIn, repo: RepoDep, request: Request) -> UserOut:
    role = repo.verify_login(body.username.strip(), body.password)
    if role is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    set_session(request, body.username.strip(), role)  # type: ignore[arg-type]
    return UserOut(username=body.username.strip(), role=role)


@app.post("/api/auth/logout")
def logout(request: Request) -> dict[str, str]:
    clear_session(request)
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=UserOut)
def me(user: UserDep) -> UserOut:
    username, role = user
    return UserOut(username=username, role=role)


@app.get("/api/customers", response_model=list[CustomerOut])
def customers(repo: RepoDep, _user: UserDep) -> list[CustomerOut]:
    return [
        CustomerOut(id=int(c["id"]), name=str(c["name"]), credit_days=int(c["credit_days"]))
        for c in repo.list_customers()
    ]


@app.post("/api/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED)
def create_customer(body: CustomerCreateIn, repo: RepoDep, _owner: OwnerDep) -> CustomerOut:
    cid = repo.upsert_customer(body.name, body.credit_days)
    row = repo.get_customer(cid)
    assert row is not None
    return CustomerOut(id=cid, name=str(row["name"]), credit_days=int(row["credit_days"]))


@app.get("/api/payments", response_model=list[PaymentOut])
def payments(
    repo: RepoDep,
    _user: UserDep,
    limit: int = Query(50, ge=1, le=200),
) -> list[PaymentOut]:
    rows = repo.list_payments_recent(limit)
    return [
        PaymentOut(
            id=int(r["id"]),
            customer_id=int(r["customer_id"]),
            customer_name=str(r["customer_name"] or ""),
            payment_date=str(r["payment_date"] or ""),
            amount=float(r["amount"] or 0),
            mode=str(r["mode"] or ""),
            reference=str(r["reference"] or ""),
        )
        for r in rows
    ]


@app.post("/api/payments", response_model=PaymentCreatedOut, status_code=status.HTTP_201_CREATED)
def create_payment(body: PaymentCreateIn, repo: RepoDep, _user: UserDep) -> PaymentCreatedOut:
    try:
        pdate = date.fromisoformat(body.payment_date.strip())
    except ValueError as e:
        raise HTTPException(status_code=400, detail="payment_date must be YYYY-MM-DD") from e
    if repo.get_customer(body.customer_id) is None:
        raise HTTPException(status_code=400, detail="Customer not found")
    try:
        pid = repo.create_payment(
            body.customer_id,
            pdate,
            body.amount,
            mode=body.mode,
            reference=body.reference,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return PaymentCreatedOut(id=pid)


@app.get("/api/dashboard", response_model=DashboardOut)
def dashboard(repo: RepoDep, _user: UserDep) -> DashboardOut:
    today = date.today()
    s = repo.dashboard_summary(today)
    return DashboardOut(
        as_of=today.isoformat(),
        total_outstanding=s.total_outstanding,
        due_today_count=s.due_today_invoice_count,
        overdue_count=s.overdue_invoice_count,
        mtd_sales_ex_gst=s.mtd_sales_ex_gst,
        mtd_collections=s.mtd_collections,
        mtd_gross_profit=s.mtd_gross_profit,
        customer_count=s.customer_count,
        invoice_count=s.invoice_count,
    )


@app.get("/api/due", response_model=list[DueRowOut])
def due_list(
    repo: RepoDep,
    _user: UserDep,
    overdue: bool = Query(False, description="Only invoices past due date"),
    due_today: bool = Query(False, description="Only invoices due today"),
) -> list[DueRowOut]:
    today = date.today()
    rows = repo.due_rows(
        today,
        only_due_today=due_today,
        only_overdue=overdue,
        due_from=None,
        due_to=None,
    )
    return [
        DueRowOut(
            invoice_id=r.invoice_id,
            invoice_no=r.invoice_no,
            customer_name=r.customer_name,
            due_date=r.due_date.isoformat(),
            outstanding=r.outstanding,
            days_overdue=r.days_overdue,
        )
        for r in rows
    ]


@app.get("/api/reminders", response_model=RemindersOut)
def reminders(repo: RepoDep, _user: UserDep) -> RemindersOut:
    today = date.today()
    items = collect_notifications(repo, today)
    return RemindersOut(
        as_of=today.isoformat(),
        items=[
            ReminderOut(
                kind=n.kind,
                severity=n.severity,
                title=n.title,
                detail=n.detail,
            )
            for n in items
        ],
        digest_text=build_owner_digest(repo, today),
    )
