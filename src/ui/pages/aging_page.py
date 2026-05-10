from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...repo import CustomerAgingRow, Repo


class _SortItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:  # type: ignore[override]
        for role in (Qt.UserRole + 1, Qt.UserRole):
            a = self.data(role)
            b = other.data(role)
            if a is not None and b is not None:
                try:
                    return a < b
                except Exception:
                    return str(a) < str(b)
        return super().__lt__(other)


class AgingPage(QWidget):
    """Receivables aging (days past due) — standard AR buckets."""

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo

        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Receivables aging")
        title.setStyleSheet("font-size:20px; font-weight:600;")
        header.addWidget(title)
        header.addStretch(1)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setMinimumHeight(32)
        self.btn_refresh.clicked.connect(lambda: self.refresh(today=date.today()))
        header.addWidget(self.btn_refresh)
        self.btn_export = QPushButton("Export customer CSV…")
        self.btn_export.setMinimumHeight(32)
        self.btn_export.clicked.connect(self._export_csv)
        header.addWidget(self.btn_export)
        layout.addLayout(header)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setStyleSheet("color:#334155; font-size:13px;")
        layout.addWidget(self.summary)

        hint = QLabel(
            "Outstanding per invoice is assigned to a bucket using its due date vs today: "
            "not yet due → Current; overdue → 1–30 / 31–60 / 61–90 / 90+ days past due."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748b; font-size:12px;")
        layout.addWidget(hint)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            [
                "Customer",
                "Current",
                "1–30 past due",
                "31–60 past due",
                "61–90 past due",
                "90+ past due",
                "Total",
            ]
        )
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.setColumnWidth(0, 220)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        self._rows_cache: list[CustomerAgingRow] = []
        self._as_of: date = date.today()

    def refresh(self, *, today: date) -> None:
        self._as_of = today
        totals, cust_rows = self._repo.receivables_aging_report(today)
        self._rows_cache = cust_rows

        self.summary.setText(
            f"As of {today.strftime('%d-%m-%Y')} — "
            f"Current: {totals.current:,.2f} · "
            f"1–30: {totals.past_1_30:,.2f} · "
            f"31–60: {totals.past_31_60:,.2f} · "
            f"61–90: {totals.past_61_90:,.2f} · "
            f"90+: {totals.past_90_plus:,.2f} · "
            f"Portfolio: {totals.grand_total():,.2f}"
        )

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(cust_rows))
        for i, row in enumerate(cust_rows):
            nm = _SortItem(row.customer_name)
            nm.setData(Qt.UserRole, row.customer_name.lower())
            self.table.setItem(i, 0, nm)

            vals = [
                row.current,
                row.past_1_30,
                row.past_31_60,
                row.past_61_90,
                row.past_90_plus,
                row.row_total(),
            ]
            for col, v in enumerate(vals, start=1):
                it = _SortItem(f"{v:,.2f}")
                it.setData(Qt.UserRole, float(v))
                it.setData(Qt.UserRole + 1, float(v))
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, col, it)

        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()

    def _export_csv(self) -> None:
        if not self._rows_cache:
            QMessageBox.information(self, "Export", "Nothing to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export receivables aging", "", "CSV (*.csv)"
        )
        if not path.strip():
            return
        p = Path(path)
        if p.suffix.lower() != ".csv":
            p = p.with_suffix(".csv")
        try:
            with p.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["report", "receivables_aging_by_customer"])
                w.writerow(["as_of_date_iso", self._as_of.isoformat()])
                w.writerow([])
                w.writerow(
                    [
                        "customer",
                        "current",
                        "past_due_1_30",
                        "past_due_31_60",
                        "past_due_61_90",
                        "past_due_90_plus",
                        "total",
                    ]
                )
                for row in self._rows_cache:
                    w.writerow(
                        [
                            row.customer_name,
                            f"{row.current:.2f}",
                            f"{row.past_1_30:.2f}",
                            f"{row.past_31_60:.2f}",
                            f"{row.past_61_90:.2f}",
                            f"{row.past_90_plus:.2f}",
                            f"{row.row_total():.2f}",
                        ]
                    )
        except OSError as e:
            QMessageBox.warning(self, "Export", str(e))
            return
        QMessageBox.information(self, "Export", f"Saved:\n{p}")
