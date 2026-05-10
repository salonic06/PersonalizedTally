from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ...repo import Repo


class HomePage(QWidget):
    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo

        layout = QVBoxLayout(self)
        title = QLabel("Dashboard")
        title.setStyleSheet("font-size:22px; font-weight:600;")
        layout.addWidget(title)

        sub = QLabel(
            "Snapshot for today’s calendar date — receivables from open balances; "
            "sales use invoice line revenue (ex‑GST); collections use payment dates; "
            "gross profit uses batch COGS where invoice lines link to costed batches."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#64748b; font-size:13px; margin-bottom: 4px;")
        layout.addWidget(sub)

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

        def card(row: int, col: int, caption: str) -> tuple[QLabel, QLabel]:
            box = QFrame()
            box.setObjectName("dashCard")
            box.setMinimumHeight(88)
            vl = QVBoxLayout(box)
            vl.setSpacing(6)
            cap = QLabel(caption)
            cap.setStyleSheet("color:#475569; font-size:12px; font-weight:600;")
            cap.setWordWrap(True)
            val = QLabel("—")
            val.setStyleSheet("font-size:22px; font-weight:700; color:#0f172a;")
            val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            foot = QLabel("")
            foot.setStyleSheet("color:#64748b; font-size:13px;")
            foot.setWordWrap(True)
            vl.addWidget(cap)
            vl.addWidget(val)
            vl.addWidget(foot)
            grid.addWidget(box, row, col)
            return val, foot

        # Receivables & cadence
        self._v_out, self._v_out_f = card(0, 0, "Total outstanding (open invoices)")
        self._v_due_t, self._v_due_t_f = card(0, 1, "Invoices with balance due today")
        self._v_due_o, self._v_due_o_f = card(0, 2, "Invoices with overdue balance")

        self._v_mtd_sales, self._v_mtd_sales_f = card(1, 0, "MTD sales (ex‑GST)")
        self._v_mtd_coll, self._v_mtd_coll_f = card(1, 1, "MTD collections (payments)")
        self._v_mtd_gap, self._v_mtd_gap_f = card(1, 2, "MTD cash gap (collections − sales)")

        self._v_mtd_gp, self._v_mtd_gp_f = card(2, 0, "MTD gross profit (est.)")
        self._v_ytd_gp, self._v_ytd_gp_f = card(2, 1, "YTD gross profit (est.)")
        self._v_mtd_inv_n, self._v_mtd_inv_n_f = card(2, 2, "MTD invoices issued (#)")

        self._v_ytd_sales, self._v_ytd_sales_f = card(3, 0, "YTD sales (ex‑GST)")
        self._v_ytd_coll, self._v_ytd_coll_f = card(3, 1, "YTD collections (payments)")
        self._v_ytd_gap, self._v_ytd_gap_f = card(3, 2, "YTD cash gap (collections − sales)")

        self._v_ytd_inv_n, self._v_ytd_inv_n_f = card(4, 0, "YTD invoices issued (#)")
        self._v_cust, self._v_cust_f = card(4, 1, "Active customers")
        self._v_items, self._v_items_f = card(4, 2, "Products in master")

        self._v_rm, self._v_rm_f = card(5, 0, "Raw materials")
        self._v_inv, self._v_inv_f = card(5, 1, "Invoices on record (all time)")
        self._v_pay, self._v_pay_f = card(5, 2, "Payments recorded (all time)")

        self._v_batches, self._v_batches_f = card(6, 0, "Production batches")
        # spare cells on row 6 col 1–2 — mini hints
        hint_box = QFrame()
        hint_box.setObjectName("dashCard")
        hvl = QVBoxLayout(hint_box)
        hc = QLabel("Tip")
        hc.setStyleSheet("color:#64748b; font-size:12px;")
        hv = QLabel("Use Due Today / Overdue in the header for collections focus.")
        hv.setWordWrap(True)
        hv.setStyleSheet("font-size:13px; color:#334155;")
        hvl.addWidget(hc)
        hvl.addWidget(hv)
        grid.addWidget(hint_box, 6, 1, 1, 2)

        scroll_lay.addLayout(grid)

        foot = QLabel(
            "Use the top search bar for customers, invoices, payments, and products. "
            "Due / Outstanding and Payments update balances with FIFO allocation."
        )
        foot.setStyleSheet("color:#475569; font-size:14px;")
        foot.setWordWrap(True)
        scroll_lay.addWidget(foot)

        scroll.setWidget(scroll_body)
        layout.addWidget(scroll, 1)

    def refresh(self) -> None:
        s = self._repo.dashboard_summary(date.today())
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

        self._v_mtd_sales.setText(f"₹{s.mtd_sales_ex_gst:,.2f}")
        self._v_mtd_sales_f.setText(f"{s.mtd_invoice_count} invoices this month")
        self._v_mtd_coll.setText(f"₹{s.mtd_collections:,.2f}")
        self._v_mtd_coll_f.setText("by payment date")
        mtd_gap = s.mtd_collections - s.mtd_sales_ex_gst
        self._v_mtd_gap.setText(f"₹{mtd_gap:,.2f}")
        self._v_mtd_gap_f.setText("positive = collected ahead of billed MTD")
        col = "#b45309" if mtd_gap < -1e-6 else "#0f172a"
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
        col_y = "#b45309" if ytd_gap < -1e-6 else "#0f172a"
        self._v_ytd_gap.setStyleSheet(f"font-size:20px; font-weight:700; color:{col_y};")

        self._v_ytd_inv_n.setText(str(s.ytd_invoice_count))
        self._v_ytd_inv_n_f.setText("calendar year to date")

        for lbl in (
            self._v_cust,
            self._v_items,
            self._v_rm,
            self._v_inv,
            self._v_pay,
            self._v_out,
            self._v_due_t,
            self._v_due_o,
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
            lbl.setStyleSheet("font-size:22px; font-weight:700; color:#0f172a;")
