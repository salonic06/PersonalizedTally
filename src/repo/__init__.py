"""Data access layer — split across helpers, models, and core Repo implementation."""

from .core import Repo
from .helpers import (
    format_batch_code,
    iso_date,
    normalize_batch_no,
    normalize_customer_name,
    normalize_rm_short_code,
    parse_iso_date,
    suggest_rm_short_code,
)
from .models import (
    AnalyticsMonthRow,
    AnalyticsYearRow,
    AuditLogRow,
    CustomerAgingRow,
    CustomerDueRow,
    DashboardSummary,
    DueRow,
    InvoiceGrossProfit,
    ReceivablesAgingTotals,
    SearchHit,
)

__all__ = [
    "Repo",
    "DueRow",
    "CustomerDueRow",
    "ReceivablesAgingTotals",
    "CustomerAgingRow",
    "AuditLogRow",
    "DashboardSummary",
    "InvoiceGrossProfit",
    "AnalyticsMonthRow",
    "AnalyticsYearRow",
    "SearchHit",
    "normalize_customer_name",
    "normalize_rm_short_code",
    "suggest_rm_short_code",
    "normalize_batch_no",
    "format_batch_code",
    "parse_iso_date",
    "iso_date",
]
