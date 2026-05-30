from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ...notifications import collect_notifications
from ...repo import Repo
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
        scroll_lay.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)

        def card(row: int, col: int, caption: str) -> tuple[QLabel, QLabel, QFrame]:
            box = QFrame()
            box.setObjectName("dashCard")
            box.setMinimumHeight(88)
            vl = QVBoxLayout(box)
            vl.setSpacing(6)
            cap = QLabel(caption)
            cap.setObjectName("dashCardCaption")
            cap.setWordWrap(True)
            val = QLabel("—")
            val.setObjectName("dashCardValue")
            val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            foot = QLabel("")
            foot.setObjectName("dashCardFoot")
            foot.setWordWrap(True)
            vl.addWidget(cap)
            vl.addWidget(val)
            vl.addWidget(foot)
            grid.addWidget(box, row, col)
            return val, foot, box

        self._v_out, self._v_out_f, self._box_out = card(0, 0, "Total outstanding (open invoices)")
        self._v_due_t, self._v_due_t_f, self._box_due_t = card(
            0, 1, "Invoices with balance due today"
        )
        self._v_due_o, self._v_due_o_f, self._box_due_o = card(
            0, 2, "Invoices with overdue balance"
        )

        self._v_mtd_sales, self._v_mtd_sales_f, _ = card(1, 0, "MTD sales (ex‑GST)")
        self._v_mtd_coll, self._v_mtd_coll_f, _ = card(1, 1, "MTD collections (payments)")
        self._v_mtd_gap, self._v_mtd_gap_f, _ = card(1, 2, "MTD cash gap (collections − sales)")

        self._v_mtd_gp, self._v_mtd_gp_f, _ = card(2, 0, "MTD gross profit (est.)")
        self._v_ytd_gp, self._v_ytd_gp_f, _ = card(2, 1, "YTD gross profit (est.)")
        self._v_mtd_inv_n, self._v_mtd_inv_n_f, _ = card(2, 2, "MTD invoices issued (#)")

        self._v_ytd_sales, self._v_ytd_sales_f, _ = card(3, 0, "YTD sales (ex‑GST)")
        self._v_ytd_coll, self._v_ytd_coll_f, _ = card(3, 1, "YTD collections (payments)")
        self._v_ytd_gap, self._v_ytd_gap_f, _ = card(3, 2, "YTD cash gap (collections − sales)")

        self._v_ytd_inv_n, self._v_ytd_inv_n_f, _ = card(4, 0, "YTD invoices issued (#)")
        self._v_cust, self._v_cust_f, _ = card(4, 1, "Active customers")
        self._v_items, self._v_items_f, _ = card(4, 2, "Products in master")

        self._v_rm, self._v_rm_f, self._box_rm = card(5, 0, "Raw materials")
        self._v_inv, self._v_inv_f, _ = card(5, 1, "Invoices on record (all time)")
        self._v_pay, self._v_pay_f, _ = card(5, 2, "Payments recorded (all time)")

        self._v_batches, self._v_batches_f, _ = card(6, 0, "Production batches")
        hint_box = QFrame()
        hint_box.setObjectName("dashCard")
        hvl = QVBoxLayout(hint_box)
        hc = QLabel("Tip")
        hc.setObjectName("dashCardCaption")
        hv = QLabel("Use Reminders in the header for low stock, due today, and overdue invoices.")
        hv.setObjectName("mutedHint")
        hv.setWordWrap(True)
        hvl.addWidget(hc)
        hvl.addWidget(hv)
        grid.addWidget(hint_box, 6, 1, 1, 2)

        scroll_lay.addLayout(grid)

        foot = QLabel(
            "Use the top search bar for customers, invoices, payments, and products. "
            "Due / Outstanding and Payments update balances with FIFO allocation."
        )
        foot.setObjectName("mutedHint")
        foot.setWordWrap(True)
        scroll_lay.addWidget(foot)

        scroll.setWidget(scroll_body)
        layout.addWidget(scroll, 1)

    def _metric_style(self, *, attention: str | None = None) -> str:
        dark = is_dark_mode_enabled(self._repo)
        if attention == "alert":
            col = "#fecdd3" if dark else "#9f1239"
            return f"font-size:22px; font-weight:700; color:{col};"
        if attention == "warn":
            col = "#fcd34d" if dark else "#b45309"
            return f"font-size:22px; font-weight:700; color:{col};"
        if attention == "stock":
            col = "#fdba74" if dark else "#c2410c"
            return f"font-size:22px; font-weight:700; color:{col};"
        base = "#eceef3" if dark else "#111827"
        return f"font-size:22px; font-weight:700; color:{base};"

    def _set_alert_banner(self, kind: str, text: str) -> None:
        self._alerts.setObjectName(f"alertBanner{kind}")
        self._alerts.setText(text)
        self._alerts.style().unpolish(self._alerts)
        self._alerts.style().polish(self._alerts)

    def _style_attention_card(
        self, box: QFrame, val: QLabel, *, attention: str | None
    ) -> None:
        if attention == "alert":
            box.setObjectName("dashCardAlert")
        elif attention == "warn":
            box.setObjectName("dashCardWarn")
        elif attention == "stock":
            box.setObjectName("dashCardStock")
        else:
            box.setObjectName("dashCard")
        val.setStyleSheet(self._metric_style(attention=attention))
        box.style().unpolish(box)
        box.style().polish(box)

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

        self._style_attention_card(self._box_out, self._v_out, attention=None)
        self._style_attention_card(
            self._box_due_t,
            self._v_due_t,
            attention="warn" if s.due_today_invoice_count > 0 else None,
        )
        self._style_attention_card(
            self._box_due_o,
            self._v_due_o,
            attention="alert" if s.overdue_invoice_count > 0 else None,
        )
        self._style_attention_card(
            self._box_rm,
            self._v_rm,
            attention="stock" if has_low_stock else None,
        )

        self._v_mtd_sales.setText(f"₹{s.mtd_sales_ex_gst:,.2f}")
        self._v_mtd_sales_f.setText(f"{s.mtd_invoice_count} invoices this month")
        self._v_mtd_coll.setText(f"₹{s.mtd_collections:,.2f}")
        self._v_mtd_coll_f.setText("by payment date")
        mtd_gap = s.mtd_collections - s.mtd_sales_ex_gst
        self._v_mtd_gap.setText(f"₹{mtd_gap:,.2f}")
        self._v_mtd_gap_f.setText("positive = collected ahead of billed MTD")
        dark = is_dark_mode_enabled(self._repo)
        gap_neg = "#fcd34d" if dark else "#b45309"
        gap_ok = "#eceef3" if dark else "#111827"
        col = gap_neg if mtd_gap < -1e-6 else gap_ok
        self._v_mtd_gap.setStyleSheet(f"font-size:20px; font-weight:700; color:{col};")

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
        col_y = gap_neg if ytd_gap < -1e-6 else gap_ok
        self._v_ytd_gap.setStyleSheet(f"font-size:20px; font-weight:700; color:{col_y};")

        self._v_ytd_inv_n.setText(str(s.ytd_invoice_count))
        self._v_ytd_inv_n_f.setText("calendar year to date")

        metric = self._metric_style()
        for lbl in (
            self._v_cust,
            self._v_items,
            self._v_inv,
            self._v_pay,
            self._v_mtd_sales,
            self._v_mtd_coll,
            self._v_mtd_gp,
            self._v_ytd_gp,
            self._v_mtd_inv_n,
            self._v_ytd_sales,
            self._v_ytd_coll,
            self._v_ytd_inv_n,
            self._v_batches,
        ):
            lbl.setStyleSheet(metric)
