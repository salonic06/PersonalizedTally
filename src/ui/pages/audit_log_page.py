from __future__ import annotations

import csv
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

from ...repo import Repo
from ..page_header import make_page_header
from ..table_empty import clear_table_body_for_fill, set_table_empty_state


class _SortItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:  # type: ignore[override]
        a = self.data(Qt.UserRole)
        b = other.data(Qt.UserRole)
        if a is not None and b is not None:
            try:
                return a < b
            except Exception:
                pass
        return super().__lt__(other)


class AuditLogPage(QWidget):
    """Recent finance / ops actions (IST timestamps; Windows user when available)."""

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo

        layout = QVBoxLayout(self)
        layout.addWidget(
            make_page_header(
                "Audit log",
                "Who changed what — invoices, payments, stock, batches, and settings (IST timestamps).",
            )
        )

        head = QHBoxLayout()
        head.addStretch(1)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setMinimumHeight(32)
        self.btn_refresh.clicked.connect(self.refresh)
        head.addWidget(self.btn_refresh)
        self.btn_export = QPushButton("Export CSV…")
        self.btn_export.setMinimumHeight(32)
        self.btn_export.clicked.connect(self._export_csv)
        head.addWidget(self.btn_export)
        layout.addLayout(head)

        hint = QLabel(
            "Timestamps are stored as **India Standard Time (IST)** wall clock. "
            "Operator is the signed-in OS user when the action ran (desktop). "
            "Pair with Settings → database backup for retention."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color:#64748b; font-size:12px;")
        layout.addWidget(hint)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(
            ["When (IST)", "Action", "Type", "ID", "Operator", "Detail"]
        )
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 152)
        self.table.setColumnWidth(1, 150)
        self.table.setColumnWidth(2, 100)
        self.table.setColumnWidth(3, 52)
        self.table.setColumnWidth(4, 100)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

        self._cached: list[tuple[str, str, str, str, str, str]] = []

    def refresh(self) -> None:
        rows = self._repo.list_audit_log(limit=800)
        self._cached = []
        self.table.setSortingEnabled(False)
        if not rows:
            set_table_empty_state(self.table, "No audit entries recorded yet.")
            self.table.setSortingEnabled(True)
            return
        clear_table_body_for_fill(self.table)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self._cached.append(
                (
                    r.created_at,
                    r.action,
                    r.entity_type,
                    str(r.entity_id or ""),
                    r.operator,
                    r.detail,
                )
            )
            w = _SortItem(r.created_at)
            w.setData(Qt.UserRole, r.id)
            self.table.setItem(i, 0, w)

            a = _SortItem(r.action)
            a.setData(Qt.UserRole, r.action.lower())
            self.table.setItem(i, 1, a)

            t = _SortItem(r.entity_type)
            t.setData(Qt.UserRole, r.entity_type.lower())
            self.table.setItem(i, 2, t)

            eid = "" if r.entity_id is None else str(r.entity_id)
            id_it = _SortItem(eid)
            id_it.setData(Qt.UserRole, r.entity_id if r.entity_id is not None else -1)
            id_it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(i, 3, id_it)

            op = _SortItem(r.operator or "—")
            op.setData(Qt.UserRole, (r.operator or "").lower())
            self.table.setItem(i, 4, op)

            d = _SortItem(r.detail)
            d.setData(Qt.UserRole, r.detail.lower())
            self.table.setItem(i, 5, d)

        self.table.setSortingEnabled(True)
        self.table.sortByColumn(0, Qt.SortOrder.DescendingOrder)

    def _export_csv(self) -> None:
        if not self._cached:
            QMessageBox.information(self, "Export", "Nothing to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export audit log", "", "CSV (*.csv)")
        if not path.strip():
            return
        p = Path(path)
        if p.suffix.lower() != ".csv":
            p = p.with_suffix(".csv")
        try:
            with p.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["report", "audit_log_export"])
                w.writerow(["timezone_note", "created_at values are IST wall clock"])
                w.writerow([])
                w.writerow(["created_at_ist", "action", "entity_type", "entity_id", "operator", "detail"])
                for row in self._cached:
                    w.writerow(row)
        except OSError as e:
            QMessageBox.warning(self, "Export", str(e))
            return
        QMessageBox.information(self, "Export", f"Saved:\n{p}")
