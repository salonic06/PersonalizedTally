from __future__ import annotations

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    status: str = "ok"
    app: str = "Personalized Tally API"


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    username: str
    role: str


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


class CustomerOut(BaseModel):
    id: int
    name: str
    credit_days: int


class CustomerCreateIn(BaseModel):
    name: str = Field(min_length=1)
    credit_days: int = Field(default=45, ge=1, le=3650)


class PaymentCreateIn(BaseModel):
    customer_id: int = Field(gt=0)
    payment_date: str = Field(description="ISO date YYYY-MM-DD")
    amount: float = Field(gt=0)
    mode: str = ""
    reference: str = ""
    notes: str = ""


class PaymentOut(BaseModel):
    id: int
    customer_id: int
    customer_name: str
    payment_date: str
    amount: float
    mode: str
    reference: str


class PaymentCreatedOut(BaseModel):
    id: int
    message: str = "Payment saved and allocated FIFO to oldest invoices."
