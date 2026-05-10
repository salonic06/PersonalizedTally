from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta


def compute_due_date(invoice_date: date, credit_days: int) -> date:
    return invoice_date + timedelta(days=int(credit_days))


def receivable_aging_bucket(due_date: date, today: date) -> str:
    """
    Classify outstanding AR by days past due (due_date vs report date).
    Returns one of: current | p1_30 | p31_60 | p61_90 | p90_plus
    """
    if due_date >= today:
        return "current"
    days_past = (today - due_date).days
    if days_past <= 30:
        return "p1_30"
    if days_past <= 60:
        return "p31_60"
    if days_past <= 90:
        return "p61_90"
    return "p90_plus"


@dataclass(frozen=True)
class Customer:
    id: int
    name: str
    credit_days: int = 45


@dataclass(frozen=True)
class Invoice:
    id: int
    customer_id: int
    invoice_no: str
    invoice_date: date
    due_date: date
    total_after_tax: float


@dataclass(frozen=True)
class Payment:
    id: int
    customer_id: int
    payment_date: date
    amount: float

