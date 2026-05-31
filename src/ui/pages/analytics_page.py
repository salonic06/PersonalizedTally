from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)



from ...repo import AnalyticsMonthRow, AnalyticsYearRow, InvoiceGrossProfit, Repo
from ..form_util import form_label, make_content_section, make_metric_card
from ..page_header import make_page_header


class _NumItem(QTableWidgetItem):
    def __init__(self, text: str, sort_val: float) -> None:
        super().__init__(text)
        self.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setData(Qt.UserRole, sort_val)

    def __lt__(self, other: QTableWidgetItem) -> bool:  # type: ignore[override]
        a = self.data(Qt.UserRole)
        b = other.data(Qt.UserRole)
        if a is not None and b is not None:
            try:
                return float(a) < float(b)
            except Exception:
                pass
        return super().__lt__(other)


@dataclass(frozen=True)
class _ChartPoint:
    label: str
    value: float


def _fmt_inr_short(v: float) -> str:
    """Compact rupee label for chart overlays."""
    av = abs(v)
    sign = "−" if v < 0 else ""
    if av >= 1e7:
        return f"{sign}₹{av / 1e7:.2f} Cr"
    if av >= 1e5:
        return f"{sign}₹{av / 1e5:.2f} L"
    if av >= 1e3:
        return f"{sign}₹{av / 1e3:.2f} k"
    return f"{sign}₹{av:.0f}"


def _month_short_label(ym: str) -> str:
    try:
        y, m = ym.split("-")
        return datetime(int(y), int(m), 1).strftime("%b %y")
    except Exception:
        return ym[5:]


class _BarChart(QWidget):
    """Simple bar chart with light grid and value callouts (no extra dependencies)."""

    def __init__(self) -> None:
        super().__init__()
        self._points: list[_ChartPoint] = []
        self._title = ""
        self._bar_color = QColor("#2563eb")
        self._value_mode: str = "currency"  # currency | percent
        self.setMinimumHeight(200)

    def set_data(
        self,
        title: str,
        points: list[_ChartPoint],
        *,
        bar_color: QColor | None = None,
        value_mode: str = "currency",
    ) -> None:
        self._title = title
        self._points = points
        self._bar_color = bar_color or QColor("#2563eb")
        self._value_mode = value_mode
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        _ = event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        h = self.height()

        bg = self.palette().color(self.backgroundRole())
        p.fillRect(0, 0, w, h, bg)

        left_axis = 52
        right_m = 14
        top = 12
        title_h = 20
        bottom = 42

        p.setPen(QPen(QColor("#0f172a")))
        f_title = QFont(p.font())
        f_title.setWeight(QFont.Weight.DemiBold)
        p.setFont(f_title)
        p.drawText(left_axis, top + 16, self._title)

        p.setFont(self.font())
        area_x = left_axis
        area_y = top + title_h
        area_w = max(10, w - left_axis - right_m)
        area_h = max(10, h - (top + title_h) - bottom)

        pts = self._points[-24:]  # up to ~24 bars for dense dashboards
        if not pts:
            p.setPen(QPen(QColor("#64748b")))
            p.drawText(area_x, area_y + 22, "No data in this period")
            return

        max_v = max(abs(x.value) for x in pts) or 1.0
        has_neg = any(x.value < 0 for x in pts)
        base_y = area_y + area_h // 2 if has_neg else area_y + area_h

        grid_pen = QPen(QColor("#e2e8f0"))
        grid_pen.setWidth(1)
        p.setPen(grid_pen)
        for gi in range(5):
            gy = area_y + int(area_h * gi / 4)
            p.drawLine(area_x, gy, area_x + area_w, gy)

        p.setPen(QPen(QColor("#94a3b8")))
        p.drawLine(area_x, base_y, area_x + area_w, base_y)

        # Y-axis max label
        p.setPen(QPen(QColor("#64748b")))
        cap = f"{max_v:.1f}%" if self._value_mode == "percent" else _fmt_inr_short(max_v)
        p.drawText(4, area_y + 12, left_axis - 8, 16, Qt.AlignRight | Qt.AlignTop, cap)

        n = len(pts)
        gap = max(4, area_w // 120)
        bar_w = max(8, int((area_w - gap * (n - 1)) / n))
        total_w = bar_w * n + gap * (n - 1)
        start_x = area_x + max(0, (area_w - total_w) // 2)

        scale_h = area_h * (0.88 if has_neg else 0.92)

        small = QFont(p.font())
        small.setPointSize(max(10, p.font().pointSize()))

        for i, pt in enumerate(pts):
            x = start_x + i * (bar_w + gap)
            val = pt.value
            bh = int((abs(val) / max_v) * scale_h)
            if val >= 0:
                y = base_y - bh
            else:
                y = base_y
            p.fillRect(x, y, bar_w, bh, self._bar_color)

            # Value above bar
            p.setFont(small)
            p.setPen(QPen(QColor("#334155")))
            cap_txt = f"{val:.1f}%" if self._value_mode == "percent" else _fmt_inr_short(val)
            ty = y - 4 if val >= 0 else y + bh + 14
            if val >= 0 and ty < area_y + 2:
                ty = area_y + 2
            p.drawText(x - 4, ty - 18, bar_w + 8, 18, Qt.AlignHCenter | Qt.AlignBottom, cap_txt)

            p.setFont(self.font())
            p.setPen(QPen(QColor("#475569")))
            p.drawText(x, area_y + area_h + 6, bar_w, 22, Qt.AlignHCenter | Qt.TextWordWrap, pt.label)


class _GroupedBarChart(QWidget):
    """Two series per period (e.g. billed sales vs cash collections by month)."""

    def __init__(self) -> None:
        super().__init__()
        self._points: list[tuple[str, float, float]] = []
        self._title = ""
        self._legend = ("Sales ex‑GST", "Collections")
        self._colors = (QColor("#2563eb"), QColor("#ea580c"))
        self.setMinimumHeight(260)

    def set_data(
        self,
        title: str,
        points: list[tuple[str, float, float]],
        *,
        legend: tuple[str, str] | None = None,
        colors: tuple[QColor, QColor] | None = None,
    ) -> None:
        self._title = title
        self._points = points[-14:]
        if legend:
            self._legend = legend
        if colors:
            self._colors = colors
        self.update()

    def paintEvent(self, event) -> None:  # type: ignore[override]
        _ = event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        bg = self.palette().color(self.backgroundRole())
        p.fillRect(0, 0, w, h, bg)

        left_axis = 56
        right_m = 16
        top = 10
        title_h = 22
        legend_h = 20
        bottom = 44

        p.setPen(QPen(QColor("#0f172a")))
        f_title = QFont(p.font())
        f_title.setWeight(QFont.Weight.DemiBold)
        p.setFont(f_title)
        p.drawText(left_axis, top + 16, self._title)

        leg_y = top + title_h + 2
        p.setFont(self.font())
        lx = left_axis
        for i, name in enumerate(self._legend):
            p.fillRect(lx, leg_y, 11, 11, self._colors[i])
            p.setPen(QPen(QColor("#475569")))
            p.drawText(lx + 15, leg_y + 11, name)
            lx += p.fontMetrics().horizontalAdvance(name) + 36

        area_y = top + title_h + legend_h + 8
        area_x = left_axis
        area_w = max(10, w - left_axis - right_m)
        area_h = max(10, h - area_y - bottom)

        pts = self._points
        if not pts:
            p.setPen(QPen(QColor("#64748b")))
            p.drawText(area_x, area_y + 22, "No data in this period")
            return

        max_v = max(max(a, b) for _, a, b in pts) or 1.0

        grid_pen = QPen(QColor("#e2e8f0"))
        grid_pen.setWidth(1)
        p.setPen(grid_pen)
        for gi in range(5):
            gy = area_y + int(area_h * gi / 4)
            p.drawLine(area_x, gy, area_x + area_w, gy)

        base_y = area_y + area_h
        p.setPen(QPen(QColor("#94a3b8")))
        p.drawLine(area_x, base_y, area_x + area_w, base_y)

        p.setPen(QPen(QColor("#64748b")))
        cap_ax = _fmt_inr_short(max_v)
        p.drawText(4, area_y + 12, left_axis - 10, 18, Qt.AlignRight | Qt.AlignTop, cap_ax)

        n = len(pts)
        gap_g = max(6, area_w // max(64, n * 8))
        inner_g = max(3, gap_g // 3)
        avail = area_w - gap_g * max(0, n - 1)
        group_w = max(28, avail // n) if n else 28
        bar_w = max(7, (group_w - inner_g) // 2)
        total_w = n * group_w + gap_g * max(0, n - 1)
        start_x = area_x + max(0, (area_w - total_w) // 2)

        scale_h = area_h * 0.86
        small = QFont(p.font())
        small.setPointSize(max(10, p.font().pointSize()))

        for i, (lab, va, vb) in enumerate(pts):
            gx = start_x + i * (group_w + gap_g)
            for j, val in enumerate((va, vb)):
                x = gx + j * (bar_w + inner_g)
                bh = int((max(0.0, val) / max_v) * scale_h)
                y = base_y - bh
                p.fillRect(x, y, bar_w, bh, self._colors[j])
                p.setFont(small)
                p.setPen(QPen(QColor("#334155")))
                cap_txt = _fmt_inr_short(val)
                ty = y - 4
                if ty < area_y + 2:
                    ty = area_y + 2
                p.drawText(x - 3, ty - 18, bar_w + 6, 18, Qt.AlignHCenter | Qt.AlignBottom, cap_txt)
            p.setFont(self.font())
            p.setPen(QPen(QColor("#475569")))
            p.drawText(gx - 2, base_y + 4, group_w + 4, 36, Qt.AlignHCenter | Qt.TextWordWrap, lab)


class _DateItem(QTableWidgetItem):
    def __init__(self, text: str, sort_key: date) -> None:
        super().__init__(text)
        self.setData(Qt.UserRole, sort_key.isoformat())

    def __lt__(self, other: QTableWidgetItem) -> bool:  # type: ignore[override]
        a, b = self.data(Qt.UserRole), other.data(Qt.UserRole)
        if a and b:
            return str(a) < str(b)
        return super().__lt__(other)


class AnalyticsPage(QWidget):
    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo

        layout = QVBoxLayout(self)
        layout.addWidget(
            make_page_header(
                "Analytics",
                "Sales, collections, margin, and concentration — invoice date filter for billed activity; "
                "cash uses payment dates in the same window.",
            )
        )

        filter_sec, filter_lay = make_content_section(
            "Date range",
            "Filter invoice gross-profit rows by invoice date. Outstanding is a live snapshot (not filtered).",
        )
        filt = QHBoxLayout()
        filt.addWidget(form_label("Invoice date from"))
        self.from_de = QDateEdit()
        self.to_de = QDateEdit()
        for w in (self.from_de, self.to_de):
            w.setCalendarPopup(True)
            w.setDisplayFormat("dd-MM-yyyy")
            w.setMinimumHeight(32)
        today = date.today()
        try:
            start = date(today.year - 1, today.month, 1)
        except ValueError:
            start = date(today.year - 1, today.month, 1)
        self.from_de.setDate(QDate(start.year, start.month, start.day))
        self.to_de.setDate(QDate(today.year, today.month, today.day))
        self.from_de.dateChanged.connect(lambda _: self.refresh())
        self.to_de.dateChanged.connect(lambda _: self.refresh())

        filt.addWidget(self.from_de)
        filt.addWidget(form_label("to"))
        filt.addWidget(self.to_de)
        filt.addStretch(1)
        filter_lay.addLayout(filt)

        self._outstanding_lbl = QLabel("")
        self._outstanding_lbl.setObjectName("analyticsStat")
        self._outstanding_lbl.setWordWrap(True)
        filter_lay.addWidget(self._outstanding_lbl)
        layout.addWidget(filter_sec)

        self._kpi_grid = QGridLayout()
        self._kpi_grid.setSpacing(14)
        self._kpi_grid.setHorizontalSpacing(14)
        self._kpi_labels: dict[str, QLabel] = {}

        def add_kpi(row: int, col: int, key: str, caption: str) -> None:
            val, foot, _, box = make_metric_card(caption)
            foot.hide()
            val.setWordWrap(True)
            val.setMinimumHeight(30)
            box.setMinimumHeight(92)
            self._kpi_grid.addWidget(box, row, col)
            self._kpi_labels[key] = val

        add_kpi(0, 0, "sales", "Sales ex‑GST (invoice dates)")
        add_kpi(0, 1, "cogs", "COGS (linked batches)")
        add_kpi(0, 2, "gp", "Gross profit")
        add_kpi(0, 3, "margin", "GP margin %")
        add_kpi(1, 0, "inv_n", "Invoices (#)")
        add_kpi(1, 1, "avg", "Avg invoice (ex‑GST)")
        add_kpi(1, 2, "cov", "Lines with COGS")
        add_kpi(1, 3, "costed_inv", "Fully costed invoices")
        add_kpi(2, 0, "bills_gst", "Billing (incl. GST)")
        add_kpi(2, 1, "gst_out", "Est. output GST")
        add_kpi(2, 2, "pay_period", "Cash in (payment dates)")
        add_kpi(2, 3, "cash_ratio", "Cash ÷ sales %")
        add_kpi(3, 0, "top_cust", "Top customer share")
        add_kpi(3, 1, "ar_snap", "Outstanding snapshot")
        add_kpi(3, 2, "gp_per_inv", "GP per invoice")
        add_kpi(3, 3, "cogs_pct", "COGS ÷ sales %")

        tabs = QTabWidget()
        layout.addWidget(tabs, 1)

        sum_w = QWidget()
        sum_outer = QVBoxLayout(sum_w)
        sum_outer.setContentsMargins(0, 0, 0, 0)

        sum_scroll = QScrollArea()
        sum_scroll.setWidgetResizable(True)
        sum_scroll.setFrameShape(QFrame.Shape.NoFrame)
        sum_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        sum_inner = QWidget()
        sum_lay = QVBoxLayout(sum_inner)
        sum_lay.setSpacing(16)

        kpi_sec, kpi_lay = make_content_section(
            "Period statistics",
            "Rollups for invoices in the selected date range.",
        )
        kpi_host = QWidget()
        kpi_host.setMinimumWidth(560)
        kpi_host.setLayout(self._kpi_grid)
        kpi_lay.addWidget(kpi_host)
        sum_lay.addWidget(kpi_sec)

        row_btns = QHBoxLayout()
        self.btn_export_month = QPushButton("Export monthly CSV…")
        self.btn_export_year = QPushButton("Export yearly CSV…")
        self.btn_export_month.setMinimumHeight(32)
        self.btn_export_year.setMinimumHeight(32)
        self.btn_export_month.clicked.connect(self._export_monthly_csv)
        self.btn_export_year.clicked.connect(self._export_yearly_csv)
        row_btns.addWidget(self.btn_export_month)
        row_btns.addWidget(self.btn_export_year)
        row_btns.addStretch(1)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setMinimumHeight(32)
        self.btn_refresh.clicked.connect(self.refresh)
        row_btns.addWidget(self.btn_refresh)
        sum_lay.addLayout(row_btns)

        charts_sec, charts_lay = make_content_section(
            "Monthly charts",
            "Compare billed activity vs collections; spot COGS pressure.",
        )
        charts_wrap = QWidget()
        charts_grid = QGridLayout(charts_wrap)
        charts_grid.setSpacing(18)

        self.chart_compare = _GroupedBarChart()
        self.chart_profit = _BarChart()
        self.chart_cogs = _BarChart()
        self.chart_margin = _BarChart()
        for ch in (self.chart_compare, self.chart_profit, self.chart_cogs, self.chart_margin):
            ch.setMinimumHeight(252)
            ch.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.MinimumExpanding,
            )
        charts_grid.addWidget(self.chart_compare, 0, 0)
        charts_grid.addWidget(self.chart_profit, 0, 1)
        charts_grid.addWidget(self.chart_cogs, 1, 0)
        charts_grid.addWidget(self.chart_margin, 1, 1)
        charts_grid.setColumnStretch(0, 1)
        charts_grid.setColumnStretch(1, 1)
        charts_lay.addWidget(charts_wrap)
        sum_lay.addWidget(charts_sec)

        top_sec, top_lay = make_content_section(
            "Top customers",
            "By ex‑GST revenue in the filtered period.",
        )
        self.tbl_top = QTableWidget(0, 5)
        self.tbl_top.setHorizontalHeaderLabels(
            ["Customer", "Revenue (ex‑GST)", "Share %", "COGS", "Gross profit"]
        )
        self.tbl_top.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_top.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_top.setMaximumHeight(240)
        self.tbl_top.verticalHeader().setDefaultSectionSize(28)
        self.tbl_top.setAlternatingRowColors(True)
        top_lay.addWidget(self.tbl_top)
        sum_lay.addWidget(top_sec)

        break_sec, break_lay = make_content_section(
            "Monthly & yearly breakdown",
            "Tables expand with your data — scroll the page to see everything.",
        )
        break_lay.addWidget(form_label("Monthly"))
        self.tbl_month = QTableWidget(0, 7)
        self.tbl_month.setHorizontalHeaderLabels(
            [
                "Month",
                "Sales (ex‑GST)",
                "COGS",
                "Gross profit",
                "Profit %",
                "Payments (in)",
                "Bill (incl. GST)",
            ]
        )
        self.tbl_month.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_month.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_month.setAlternatingRowColors(True)
        self.tbl_month.verticalHeader().setDefaultSectionSize(28)
        self.tbl_month.setMinimumHeight(200)
        break_lay.addWidget(self.tbl_month)

        break_lay.addSpacing(8)
        break_lay.addWidget(form_label("Yearly"))
        self.tbl_year = QTableWidget(0, 7)
        self.tbl_year.setHorizontalHeaderLabels(
            [
                "Year",
                "Sales (ex‑GST)",
                "COGS",
                "Gross profit",
                "Profit %",
                "Payments (in)",
                "Bill (incl. GST)",
            ]
        )
        self.tbl_year.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_year.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_year.setAlternatingRowColors(True)
        self.tbl_year.verticalHeader().setDefaultSectionSize(28)
        self.tbl_year.setMinimumHeight(160)
        break_lay.addWidget(self.tbl_year)
        sum_lay.addWidget(break_sec)

        sum_scroll.setWidget(sum_inner)
        sum_outer.addWidget(sum_scroll, 1)

        tabs.addTab(sum_w, "Summary")

        inv_w = QWidget()
        inv_lay = QVBoxLayout(inv_w)
        inv_lay.setContentsMargins(0, 0, 0, 0)

        inv_sec, inv_body = make_content_section(
            "Invoices in period",
            "Per-invoice gross profit for the selected date range.",
        )
        inv_toolbar = QHBoxLayout()
        self.btn_export_inv = QPushButton("Export invoices CSV…")
        self.btn_export_inv.setMinimumHeight(32)
        self.btn_export_inv.clicked.connect(self._export_invoices_csv)
        inv_toolbar.addWidget(self.btn_export_inv)
        inv_toolbar.addStretch(1)
        inv_body.addLayout(inv_toolbar)

        self.tbl_inv = QTableWidget(0, 8)
        self.tbl_inv.setHorizontalHeaderLabels(
            [
                "Date",
                "Invoice",
                "Customer",
                "Sales (ex‑GST)",
                "COGS",
                "Gross profit",
                "Profit %",
                "COGS full",
            ]
        )
        self.tbl_inv.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tbl_inv.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl_inv.setSortingEnabled(True)
        self.tbl_inv.setAlternatingRowColors(True)
        inv_body.addWidget(self.tbl_inv)
        inv_lay.addWidget(inv_sec)
        tabs.addTab(inv_w, "By invoice")

        self._inv_rows: list[InvoiceGrossProfit] = []
        self._month_rows: list[AnalyticsMonthRow] = []
        self._year_rows: list[AnalyticsYearRow] = []

    def refresh(self) -> None:
        today = date.today()
        dash = self._repo.dashboard_summary(today)
        self._outstanding_lbl.setText(
            f"Current total outstanding (open invoices): ₹{dash.total_outstanding:,.2f}"
        )

        inv_all = self._repo.list_invoice_gross_profits()
        d0 = self.from_de.date().toPython()  # type: ignore[attr-defined]
        d1 = self.to_de.date().toPython()  # type: ignore[attr-defined]
        if d0 > d1:
            d0, d1 = d1, d0
        self._inv_rows = [r for r in inv_all if d0 <= r.invoice_date <= d1]
        self._month_rows = self._repo.analytics_monthly_rows(self._inv_rows, include_payments=True)
        self._year_rows = self._repo.analytics_yearly_rows(self._inv_rows, include_payments=True)

        self._fill_kpis(self._inv_rows, d0, d1, dash.total_outstanding)
        self._fill_top_customers(self._inv_rows)
        self._fill_month(self._month_rows)
        self._fill_year(self._year_rows)
        self._fill_invoices(self._inv_rows)
        self._fill_charts(self._month_rows, d0, d1)

    def _fill_kpis(
        self,
        rows: list[InvoiceGrossProfit],
        d0: date,
        d1: date,
        outstanding: float,
    ) -> None:
        pay_period = self._repo.payments_total_in_date_range(d0, d1)
        self._kpi_labels["ar_snap"].setText(f"₹{outstanding:,.2f}")
        self._kpi_labels["pay_period"].setText(f"₹{pay_period:,.2f}")

        if not rows:
            z = "₹0"
            self._kpi_labels["sales"].setText(z)
            self._kpi_labels["cogs"].setText(z)
            self._kpi_labels["gp"].setText(z)
            self._kpi_labels["margin"].setText("—")
            self._kpi_labels["inv_n"].setText("0")
            self._kpi_labels["avg"].setText("—")
            self._kpi_labels["cov"].setText("—")
            self._kpi_labels["costed_inv"].setText("—")
            self._kpi_labels["bills_gst"].setText(z)
            self._kpi_labels["gst_out"].setText(z)
            self._kpi_labels["cash_ratio"].setText("—")
            self._kpi_labels["top_cust"].setText("—")
            self._kpi_labels["gp_per_inv"].setText("—")
            self._kpi_labels["cogs_pct"].setText("—")
            return

        sales = sum(r.revenue_ex_gst for r in rows)
        cogs = sum(r.cogs for r in rows)
        gp = sales - cogs
        margin = (gp / sales * 100.0) if sales > 1e-12 else 0.0
        n = len(rows)
        avg = sales / n if n else 0.0
        lc = sum(r.line_count for r in rows)
        lw = sum(r.lines_with_cogs for r in rows)
        cov = (lw / lc * 100.0) if lc > 0 else 0.0
        n_costed = sum(1 for r in rows if r.cogs_complete)
        bills = sum(r.total_after_tax for r in rows)
        gst_est = sum(max(0.0, r.total_after_tax - r.revenue_ex_gst) for r in rows)
        cash_pct = (pay_period / sales * 100.0) if sales > 1e-12 else 0.0
        cogs_pct = (cogs / sales * 100.0) if sales > 1e-12 else 0.0
        gp_per = gp / n if n else 0.0

        agg_rev: dict[str, float] = defaultdict(float)
        for r in rows:
            agg_rev[r.customer_name] += r.revenue_ex_gst
        top_name, top_amt = max(agg_rev.items(), key=lambda kv: kv[1])
        top_share = (top_amt / sales * 100.0) if sales > 1e-12 else 0.0

        self._kpi_labels["sales"].setText(f"₹{sales:,.2f}")
        self._kpi_labels["cogs"].setText(f"₹{cogs:,.2f}")
        self._kpi_labels["gp"].setText(f"₹{gp:,.2f}")
        self._kpi_labels["margin"].setText(f"{margin:.2f}%")
        self._kpi_labels["inv_n"].setText(str(n))
        self._kpi_labels["avg"].setText(f"₹{avg:,.2f}")
        self._kpi_labels["cov"].setText(f"{lw}/{lc} ({cov:.1f}%)")
        self._kpi_labels["costed_inv"].setText(f"{n_costed}/{n} ({n_costed / n * 100:.1f}%)")
        self._kpi_labels["bills_gst"].setText(f"₹{bills:,.2f}")
        self._kpi_labels["gst_out"].setText(f"₹{gst_est:,.2f}")
        self._kpi_labels["cash_ratio"].setText(f"{cash_pct:.1f}%")
        self._kpi_labels["top_cust"].setText(f"{top_name}\n{top_share:.1f}% of period sales")
        self._kpi_labels["gp_per_inv"].setText(f"₹{gp_per:,.2f}")
        self._kpi_labels["cogs_pct"].setText(f"{cogs_pct:.1f}%")

    def _fill_top_customers(self, rows: list[InvoiceGrossProfit]) -> None:
        self.tbl_top.setRowCount(0)
        self.tbl_top.setSortingEnabled(False)
        if not rows:
            return
        agg_rev: dict[str, float] = defaultdict(float)
        agg_cogs: dict[str, float] = defaultdict(float)
        for r in rows:
            agg_rev[r.customer_name] += r.revenue_ex_gst
            agg_cogs[r.customer_name] += r.cogs
        total = sum(agg_rev.values()) or 1.0
        ranked = sorted(agg_rev.items(), key=lambda kv: -kv[1])[:12]
        for name, rev in ranked:
            cg = agg_cogs[name]
            gpr = rev - cg
            share = rev / total * 100.0
            i = self.tbl_top.rowCount()
            self.tbl_top.insertRow(i)
            self.tbl_top.setItem(i, 0, QTableWidgetItem(name))
            self.tbl_top.setItem(i, 1, _NumItem(f"{rev:,.2f}", rev))
            self.tbl_top.setItem(i, 2, _NumItem(f"{share:.1f}", share))
            self.tbl_top.setItem(i, 3, _NumItem(f"{cg:,.2f}", cg))
            self.tbl_top.setItem(i, 4, _NumItem(f"{gpr:,.2f}", gpr))

    def _fill_charts(self, months: list[AnalyticsMonthRow], d0: date, d1: date) -> None:
        # Chronological left→right for readability
        seq = list(reversed(months))
        pts_profit = [_ChartPoint(label=_month_short_label(m.year_month), value=m.gross_profit) for m in seq]
        pts_margin = []
        pts_cogs = [_ChartPoint(label=_month_short_label(m.year_month), value=m.cogs) for m in seq]
        pair_pts: list[tuple[str, float, float]] = []
        for m in seq:
            pct = (m.gross_profit / m.sales_ex_gst * 100.0) if m.sales_ex_gst > 1e-12 else 0.0
            pts_margin.append(_ChartPoint(label=_month_short_label(m.year_month), value=pct))
            pair_pts.append(
                (
                    _month_short_label(m.year_month),
                    m.sales_ex_gst,
                    m.payments_received,
                )
            )

        rng = f"{d0.strftime('%d %b %y')} — {d1.strftime('%d %b %y')}"
        self.chart_compare.set_data(
            f"Billed sales vs collections by month ({rng})",
            pair_pts,
            legend=("Sales ex‑GST", "Collections (cash)"),
            colors=(QColor("#2563eb"), QColor("#ea580c")),
        )
        self.chart_profit.set_data(
            f"Gross profit by month ({rng})",
            pts_profit,
            bar_color=QColor("#059669"),
            value_mode="currency",
        )
        self.chart_cogs.set_data(
            f"COGS by month ({rng})",
            pts_cogs,
            bar_color=QColor("#475569"),
            value_mode="currency",
        )
        self.chart_margin.set_data(
            f"Margin % by month (GP ÷ sales) ({rng})",
            pts_margin,
            bar_color=QColor("#7c3aed"),
            value_mode="percent",
        )

    def _fill_month(self, rows: list[AnalyticsMonthRow]) -> None:
        self.tbl_month.setRowCount(0)
        self.tbl_month.setSortingEnabled(False)
        for r in rows:
            gp = r.gross_profit
            pct = (gp / r.sales_ex_gst * 100.0) if r.sales_ex_gst > 1e-12 else 0.0
            i = self.tbl_month.rowCount()
            self.tbl_month.insertRow(i)
            self.tbl_month.setItem(i, 0, QTableWidgetItem(r.year_month))
            self.tbl_month.setItem(i, 1, _NumItem(f"{r.sales_ex_gst:,.2f}", r.sales_ex_gst))
            self.tbl_month.setItem(i, 2, _NumItem(f"{r.cogs:,.2f}", r.cogs))
            self.tbl_month.setItem(i, 3, _NumItem(f"{gp:,.2f}", gp))
            self.tbl_month.setItem(i, 4, _NumItem(f"{pct:,.2f}", pct))
            self.tbl_month.setItem(i, 5, _NumItem(f"{r.payments_received:,.2f}", r.payments_received))
            self.tbl_month.setItem(i, 6, _NumItem(f"{r.bill_total_after_tax:,.2f}", r.bill_total_after_tax))
        self.tbl_month.setSortingEnabled(True)

    def _fill_year(self, rows: list[AnalyticsYearRow]) -> None:
        self.tbl_year.setRowCount(0)
        self.tbl_year.setSortingEnabled(False)
        for r in rows:
            gp = r.gross_profit
            pct = (gp / r.sales_ex_gst * 100.0) if r.sales_ex_gst > 1e-12 else 0.0
            i = self.tbl_year.rowCount()
            self.tbl_year.insertRow(i)
            self.tbl_year.setItem(i, 0, QTableWidgetItem(r.year))
            self.tbl_year.setItem(i, 1, _NumItem(f"{r.sales_ex_gst:,.2f}", r.sales_ex_gst))
            self.tbl_year.setItem(i, 2, _NumItem(f"{r.cogs:,.2f}", r.cogs))
            self.tbl_year.setItem(i, 3, _NumItem(f"{gp:,.2f}", gp))
            self.tbl_year.setItem(i, 4, _NumItem(f"{pct:,.2f}", pct))
            self.tbl_year.setItem(i, 5, _NumItem(f"{r.payments_received:,.2f}", r.payments_received))
            self.tbl_year.setItem(i, 6, _NumItem(f"{r.bill_total_after_tax:,.2f}", r.bill_total_after_tax))
        self.tbl_year.setSortingEnabled(True)

    def _fill_invoices(self, rows: list[InvoiceGrossProfit]) -> None:
        sort_was = self.tbl_inv.isSortingEnabled()
        self.tbl_inv.setSortingEnabled(False)
        self.tbl_inv.setRowCount(0)
        for r in rows:
            i = self.tbl_inv.rowCount()
            self.tbl_inv.insertRow(i)
            self.tbl_inv.setItem(
                i,
                0,
                _DateItem(r.invoice_date.strftime("%d-%m-%Y"), r.invoice_date),
            )
            self.tbl_inv.setItem(i, 1, QTableWidgetItem(r.invoice_no))
            self.tbl_inv.setItem(i, 2, QTableWidgetItem(r.customer_name))
            self.tbl_inv.setItem(i, 3, _NumItem(f"{r.revenue_ex_gst:,.2f}", r.revenue_ex_gst))
            self.tbl_inv.setItem(i, 4, _NumItem(f"{r.cogs:,.2f}", r.cogs))
            self.tbl_inv.setItem(i, 5, _NumItem(f"{r.gross_profit:,.2f}", r.gross_profit))
            pct = (r.gross_profit / r.revenue_ex_gst * 100.0) if r.revenue_ex_gst > 1e-12 else 0.0
            self.tbl_inv.setItem(i, 6, _NumItem(f"{pct:,.2f}", pct))
            full = "Yes" if r.cogs_complete else "No"
            it = QTableWidgetItem(full)
            it.setData(Qt.UserRole, 1.0 if r.cogs_complete else 0.0)
            it.setToolTip(f"COGS coverage: {r.lines_with_cogs}/{r.line_count} lines")
            self.tbl_inv.setItem(i, 7, it)
        self.tbl_inv.setSortingEnabled(sort_was)

    def _export_monthly_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export monthly analytics", "", "CSV (*.csv)"
        )
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() != ".csv":
            p = p.with_suffix(".csv")
        try:
            with p.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(
                    [
                        "year_month",
                        "sales_ex_gst",
                        "cogs",
                        "gross_profit",
                        "profit_pct",
                        "payments_received",
                        "bill_total_after_tax",
                    ]
                )
                for r in self._month_rows:
                    gp = r.gross_profit
                    pct = (gp / r.sales_ex_gst * 100.0) if r.sales_ex_gst > 1e-12 else 0.0
                    w.writerow(
                        [
                            r.year_month,
                            f"{r.sales_ex_gst:.2f}",
                            f"{r.cogs:.2f}",
                            f"{gp:.2f}",
                            f"{pct:.2f}",
                            f"{r.payments_received:.2f}",
                            f"{r.bill_total_after_tax:.2f}",
                        ]
                    )
        except OSError as e:
            QMessageBox.warning(self, "Export", str(e))
            return
        QMessageBox.information(self, "Export", f"Saved:\n{p}")

    def _export_yearly_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export yearly analytics", "", "CSV (*.csv)"
        )
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() != ".csv":
            p = p.with_suffix(".csv")
        try:
            with p.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(
                    [
                        "year",
                        "sales_ex_gst",
                        "cogs",
                        "gross_profit",
                        "profit_pct",
                        "payments_received",
                        "bill_total_after_tax",
                    ]
                )
                for r in self._year_rows:
                    gp = r.gross_profit
                    pct = (gp / r.sales_ex_gst * 100.0) if r.sales_ex_gst > 1e-12 else 0.0
                    w.writerow(
                        [
                            r.year,
                            f"{r.sales_ex_gst:.2f}",
                            f"{r.cogs:.2f}",
                            f"{gp:.2f}",
                            f"{pct:.2f}",
                            f"{r.payments_received:.2f}",
                            f"{r.bill_total_after_tax:.2f}",
                        ]
                    )
        except OSError as e:
            QMessageBox.warning(self, "Export", str(e))
            return
        QMessageBox.information(self, "Export", f"Saved:\n{p}")

    def _export_invoices_csv(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export invoice gross profit", "", "CSV (*.csv)"
        )
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() != ".csv":
            p = p.with_suffix(".csv")
        try:
            with p.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(
                    [
                        "invoice_date",
                        "invoice_no",
                        "customer",
                        "sales_ex_gst",
                        "cogs",
                        "gross_profit",
                        "profit_pct",
                        "lines_with_cogs",
                        "line_count",
                        "cogs_complete",
                    ]
                )
                for r in self._inv_rows:
                    pct = (r.gross_profit / r.revenue_ex_gst * 100.0) if r.revenue_ex_gst > 1e-12 else 0.0
                    w.writerow(
                        [
                            r.invoice_date.isoformat(),
                            r.invoice_no,
                            r.customer_name,
                            f"{r.revenue_ex_gst:.2f}",
                            f"{r.cogs:.2f}",
                            f"{r.gross_profit:.2f}",
                            f"{pct:.2f}",
                            r.lines_with_cogs,
                            r.line_count,
                            "yes" if r.cogs_complete else "no",
                        ]
                    )
        except OSError as e:
            QMessageBox.warning(self, "Export", str(e))
            return
        QMessageBox.information(self, "Export", f"Saved:\n{p}")
