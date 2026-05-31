from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ...notifications import collect_notifications
from ...repo import Repo
from ..form_util import form_hint, make_content_section, make_metric_card, set_metric_card_style
from ..page_header import make_page_header
from ..theme import is_dark_mode_enabled


class HomePage(QWidget):
    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo

        layout = QVBoxLayout(self)
        layout.addWidget(
            make_page_header(
                "Dashboard",
                "Today’s snapshot — open receivables, MTD/YTD sales and collections, gross profit where batches are costed.",
            )
        )

        self._alerts = QLabel("")
        self._alerts.setWordWrap(True)
        layout.addWidget(self._alerts)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        scroll_body = QWidget()
        scroll_lay = QVBoxLayout(scroll_body)
        scroll_lay.setSpacing(16)

        recv_sec, recv_lay = make_content_section(
            "Receivables",
            "Open invoice balances and due-date alerts for today.",
        )
        recv_grid = QGridLayout()
        recv_grid.setSpacing(12)
        for c in range(3):
            recv_grid.setColumnStretch(c, 1)

        self._v_out, self._v_out_f, _, self._box_out = make_metric_card(
            "Total outstanding (open invoices)"
        )
        self._v_due_t, self._v_due_t_f, _, self._box_due_t = make_metric_card(
            "Invoices with balance due today"
        )
        self._v_due_o, self._v_due_o_f, _, self._box_due_o = make_metric_card(
            "Invoices with overdue balance"
        )
        recv_grid.addWidget(self._box_out, 0, 0)
        recv_grid.addWidget(self._box_due_t, 0, 1)
        recv_grid.addWidget(self._box_due_o, 0, 2)
        recv_lay.addLayout(recv_grid)
        scroll_lay.addWidget(recv_sec)

        perf_sec, perf_lay = make_content_section(
            "Sales & collections",
            "Month-to-date and year-to-date billed sales, cash collected, and estimated gross profit.",
        )
        perf_grid = QGridLayout()
        perf_grid.setSpacing(12)
        for c in range(3):
            perf_grid.setColumnStretch(c, 1)

        self._v_mtd_sales, self._v_mtd_sales_f, _, box_mtd_sales = make_metric_card("MTD sales (ex‑GST)")
        self._v_mtd_coll, self._v_mtd_coll_f, _, box_mtd_coll = make_metric_card("MTD collections (payments)")
        self._v_mtd_gap, self._v_mtd_gap_f, _, box_mtd_gap = make_metric_card("MTD cash gap (collections − sales)")
        self._v_mtd_gp, self._v_mtd_gp_f, _, box_mtd_gp = make_metric_card("MTD gross profit (est.)")
        self._v_ytd_gp, self._v_ytd_gp_f, _, box_ytd_gp = make_metric_card("YTD gross profit (est.)")
        self._v_mtd_inv_n, self._v_mtd_inv_n_f, _, box_mtd_inv = make_metric_card("MTD invoices issued (#)")
        self._v_ytd_sales, self._v_ytd_sales_f, _, box_ytd_sales = make_metric_card("YTD sales (ex‑GST)")
        self._v_ytd_coll, self._v_ytd_coll_f, _, box_ytd_coll = make_metric_card("YTD collections (payments)")
        self._v_ytd_gap, self._v_ytd_gap_f, _, box_ytd_gap = make_metric_card("YTD cash gap (collections − sales)")
        self._v_ytd_inv_n, self._v_ytd_inv_n_f, _, box_ytd_inv = make_metric_card("YTD invoices issued (#)")

        perf_grid.addWidget(box_mtd_sales, 0, 0)
        perf_grid.addWidget(box_mtd_coll, 0, 1)
        perf_grid.addWidget(box_mtd_gap, 0, 2)
        perf_grid.addWidget(box_mtd_gp, 1, 0)
        perf_grid.addWidget(box_ytd_gp, 1, 1)
        perf_grid.addWidget(box_mtd_inv, 1, 2)
        perf_grid.addWidget(box_ytd_sales, 2, 0)
        perf_grid.addWidget(box_ytd_coll, 2, 1)
        perf_grid.addWidget(box_ytd_gap, 2, 2)
        perf_grid.addWidget(box_ytd_inv, 3, 0)
        perf_lay.addLayout(perf_grid)
        scroll_lay.addWidget(perf_sec)

        master_sec, master_lay = make_content_section(
            "Master data",
            "Counts across customers, products, stock, and production.",
        )
        master_grid = QGridLayout()
        master_grid.setSpacing(12)
        for c in range(3):
            master_grid.setColumnStretch(c, 1)

        self._v_cust, self._v_cust_f, _, box_cust = make_metric_card("Active customers")
        self._v_items, self._v_items_f, _, box_items = make_metric_card("Products in master")
        self._v_rm, self._v_rm_f, _, self._box_rm = make_metric_card("Raw materials")
        self._v_inv, self._v_inv_f, _, box_inv = make_metric_card("Invoices on record (all time)")
        self._v_pay, self._v_pay_f, _, box_pay = make_metric_card("Payments recorded (all time)")
        self._v_batches, self._v_batches_f, _, box_batches = make_metric_card("Production batches")

        master_grid.addWidget(box_cust, 0, 0)
        master_grid.addWidget(box_items, 0, 1)
        master_grid.addWidget(self._box_rm, 0, 2)
        master_grid.addWidget(box_inv, 1, 0)
        master_grid.addWidget(box_pay, 1, 1)
        master_grid.addWidget(box_batches, 1, 2)
        master_lay.addLayout(master_grid)
        scroll_lay.addWidget(master_sec)

        scroll_lay.addWidget(
            form_hint(
                "Use the top search bar for customers, invoices, payments, and products. "
                "Click Reminders in the header for low stock, due today, and overdue."
            )
        )
        scroll_lay.addStretch(1)

        scroll.setWidget(scroll_body)
        layout.addWidget(scroll, 1)

    def _gap_value_style(self, gap: float) -> str:
        dark = is_dark_mode_enabled(self._repo)
        gap_neg = "#fcd34d" if dark else "#b45309"
        gap_ok = "#eceef3" if dark else "#111827"
        col = gap_neg if gap < -1e-6 else gap_ok
        return f"font-size:20px; font-weight:700; color:{col};"

    def _set_alert_banner(self, kind: str, text: str) -> None:
        self._alerts.setObjectName(f"alertBanner{kind}")
        self._alerts.setText(text)
        self._alerts.style().unpolish(self._alerts)
        self._alerts.style().polish(self._alerts)

    def refresh_alerts(self) -> None:
        alerts = collect_notifications(self._repo, date.today())
        if not alerts:
            self._set_alert_banner(
                "Ok", "No reminders — stock and customer dues look fine for today."
            )
            return
        critical = sum(1 for a in alerts if a.severity == "critical")
        warn = sum(1 for a in alerts if a.severity == "warning")
        parts = [f"{len(alerts)} reminder{'s' if len(alerts) != 1 else ''}"]
        if critical:
            parts.append(f"{critical} overdue")
        if warn:
            parts.append(f"{warn} stock")
        preview = " · ".join(a.title for a in alerts[:3])
        if len(alerts) > 3:
            preview += f" · +{len(alerts) - 3} more"
        kind = "Warn" if critical or warn else "Info"
        self._set_alert_banner(
            kind,
            f"{' — '.join(parts)}: {preview}. Click Reminders in the header for invoice details.",
        )

    def refresh(self) -> None:
        self.refresh_alerts()
        s = self._repo.dashboard_summary(date.today())
        alerts = collect_notifications(self._repo, date.today())
        has_low_stock = any(a.kind == "reorder_low" for a in alerts)

        self._v_cust.setText(str(s.customer_count))
        self._v_items.setText(str(s.item_count))
        self._v_rm.setText(str(s.raw_material_count))
        self._v_inv.setText(str(s.invoice_count))
        self._v_pay.setText(str(s.payment_count))
        self._v_out.setText(f"₹{s.total_outstanding:,.2f}")
        self._v_out_f.setText("")
        self._v_due_t.setText(str(s.due_today_invoice_count))
        self._v_due_t_f.setText("")
        self._v_due_o.setText(str(s.overdue_invoice_count))
        self._v_due_o_f.setText("")
        self._v_batches.setText(str(s.production_batch_count))
        self._v_batches_f.setText("")

        set_metric_card_style(self._box_out, self._v_out)
        set_metric_card_style(
            self._box_due_t, self._v_due_t, warn=s.due_today_invoice_count > 0
        )
        set_metric_card_style(
            self._box_due_o, self._v_due_o, alert=s.overdue_invoice_count > 0
        )
        set_metric_card_style(self._box_rm, self._v_rm, stock=has_low_stock)

        self._v_mtd_sales.setText(f"₹{s.mtd_sales_ex_gst:,.2f}")
        self._v_mtd_sales_f.setText(f"{s.mtd_invoice_count} invoices this month")
        self._v_mtd_coll.setText(f"₹{s.mtd_collections:,.2f}")
        self._v_mtd_coll_f.setText("by payment date")
        mtd_gap = s.mtd_collections - s.mtd_sales_ex_gst
        self._v_mtd_gap.setText(f"₹{mtd_gap:,.2f}")
        self._v_mtd_gap_f.setText("positive = collected ahead of billed MTD")
        self._v_mtd_gap.setStyleSheet(self._gap_value_style(mtd_gap))

        mtd_m = (
            (s.mtd_gross_profit / s.mtd_sales_ex_gst * 100.0) if s.mtd_sales_ex_gst > 1e-9 else 0.0
        )
        self._v_mtd_gp.setText(f"₹{s.mtd_gross_profit:,.2f}")
        self._v_mtd_gp_f.setText(f"{mtd_m:.1f}% margin · COGS ₹{s.mtd_cogs:,.2f}")

        ytd_m = (
            (s.ytd_gross_profit / s.ytd_sales_ex_gst * 100.0) if s.ytd_sales_ex_gst > 1e-9 else 0.0
        )
        self._v_ytd_gp.setText(f"₹{s.ytd_gross_profit:,.2f}")
        self._v_ytd_gp_f.setText(f"{ytd_m:.1f}% margin · COGS ₹{s.ytd_cogs:,.2f}")

        self._v_mtd_inv_n.setText(str(s.mtd_invoice_count))
        self._v_mtd_inv_n_f.setText("calendar month to date")

        self._v_ytd_sales.setText(f"₹{s.ytd_sales_ex_gst:,.2f}")
        self._v_ytd_sales_f.setText("")
        self._v_ytd_coll.setText(f"₹{s.ytd_collections:,.2f}")
        self._v_ytd_coll_f.setText("")
        ytd_gap = s.ytd_collections - s.ytd_sales_ex_gst
        self._v_ytd_gap.setText(f"₹{ytd_gap:,.2f}")
        self._v_ytd_gap_f.setText("")
        self._v_ytd_gap.setStyleSheet(self._gap_value_style(ytd_gap))

        self._v_ytd_inv_n.setText(str(s.ytd_invoice_count))
        self._v_ytd_inv_n_f.setText("calendar year to date")
