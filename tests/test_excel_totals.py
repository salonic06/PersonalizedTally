from __future__ import annotations

from src.excel_generate import InvoiceLine, compute_gst_invoice_totals


def test_compute_gst_invoice_totals_default_rate() -> None:
    lines = [
        InvoiceLine(description="A", hsn="123", qty=2, unit="Nos", rate=100.0),
        InvoiceLine(description="B", hsn="456", qty=1, unit="Kg", rate=50.0),
    ]
    sub, gst, total = compute_gst_invoice_totals(lines)
    assert sub == 250.0
    assert gst == 45.0
    assert total == 295.0


def test_compute_gst_invoice_totals_empty() -> None:
    assert compute_gst_invoice_totals([]) == (0.0, 0.0, 0.0)
