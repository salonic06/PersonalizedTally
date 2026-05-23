from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from src.db.conn import connect
from src.db.migrate import migrate
from src.notifications import collect_notifications
from src.owner_digest import build_owner_digest
from src.paths import get_paths

from .deps import RepoDep
from .schemas import DashboardOut, DueRowOut, HealthOut, ReminderOut, RemindersOut


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
    description="Read-only HTTP API over the desktop app's SQLite database (portfolio slice).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut()


@app.get("/api/dashboard", response_model=DashboardOut)
def dashboard(repo: RepoDep) -> DashboardOut:
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
def reminders(repo: RepoDep) -> RemindersOut:
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
