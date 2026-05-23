from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class DueRow:
    customer_id: int
    customer_name: str
    invoice_id: int
    invoice_no: str
    invoice_date: date
    due_date: date
    outstanding: float
    days_overdue: int
    excel_path: str | None = None


@dataclass(frozen=True)
class CustomerDueRow:
    customer_id: int
    customer_name: str
    outstanding: float
    oldest_due_date: date
    invoice_count: int
    days_overdue: int


@dataclass(frozen=True)
class ReceivablesAgingTotals:
    current: float
    past_1_30: float
    past_31_60: float
    past_61_90: float
    past_90_plus: float

    def grand_total(self) -> float:
        return (
            self.current
            + self.past_1_30
            + self.past_31_60
            + self.past_61_90
            + self.past_90_plus
        )


@dataclass(frozen=True)
class CustomerAgingRow:
    customer_id: int
    customer_name: str
    current: float
    past_1_30: float
    past_31_60: float
    past_61_90: float
    past_90_plus: float

    def row_total(self) -> float:
        return (
            self.current
            + self.past_1_30
            + self.past_31_60
            + self.past_61_90
            + self.past_90_plus
        )


@dataclass(frozen=True)
class AuditLogRow:
    id: int
    created_at: str
    action: str
    entity_type: str
    entity_id: int | None
    detail: str
    operator: str


@dataclass(frozen=True)
class DashboardSummary:
    customer_count: int
    item_count: int
    raw_material_count: int
    production_batch_count: int
    invoice_count: int
    payment_count: int
    total_outstanding: float
    due_today_invoice_count: int
    overdue_invoice_count: int
    mtd_sales_ex_gst: float
    ytd_sales_ex_gst: float
    mtd_collections: float
    ytd_collections: float
    mtd_invoice_count: int
    ytd_invoice_count: int
    mtd_cogs: float
    ytd_cogs: float
    mtd_gross_profit: float
    ytd_gross_profit: float


@dataclass(frozen=True)
class InvoiceGrossProfit:
    invoice_id: int
    invoice_no: str
    invoice_date: date
    customer_name: str
    revenue_ex_gst: float
    total_after_tax: float
    cogs: float
    gross_profit: float
    line_count: int
    lines_with_cogs: int
    cogs_complete: bool


@dataclass(frozen=True)
class AnalyticsMonthRow:
    year_month: str
    sales_ex_gst: float
    bill_total_after_tax: float
    est_output_gst: float
    payments_received: float
    cogs: float
    gross_profit: float


@dataclass(frozen=True)
class AnalyticsYearRow:
    year: str
    sales_ex_gst: float
    bill_total_after_tax: float
    est_output_gst: float
    payments_received: float
    cogs: float
    gross_profit: float


@dataclass(frozen=True)
class SearchHit:
    kind: str
    record_id: int
    title: str
    detail: str
    customer_id: int | None = None
    invoice_id: int | None = None
    excel_path: str | None = None
    raw_material_id: int | None = None
