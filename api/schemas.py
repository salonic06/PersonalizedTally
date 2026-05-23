from __future__ import annotations

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    status: str = "ok"
    app: str = "Personalized Tally API"


class DashboardOut(BaseModel):
    as_of: str
    total_outstanding: float
    due_today_count: int
    overdue_count: int
    mtd_sales_ex_gst: float
    mtd_collections: float
    mtd_gross_profit: float
    customer_count: int
    invoice_count: int


class DueRowOut(BaseModel):
    invoice_id: int
    invoice_no: str
    customer_name: str
    due_date: str
    outstanding: float
    days_overdue: int


class ReminderOut(BaseModel):
    kind: str
    severity: str
    title: str
    detail: str


class RemindersOut(BaseModel):
    as_of: str
    items: list[ReminderOut] = Field(default_factory=list)
    digest_text: str = ""
