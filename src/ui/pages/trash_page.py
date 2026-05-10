from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...db.conn import transaction
from ...repo import Repo


class TrashPage(QWidget):
    """Restore soft-deleted customers, invoices, payments, and products."""

    data_changed = Signal()

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo

        layout = QVBoxLayout(self)
        title = QLabel("Trash (restore)")
        title.setStyleSheet("font-size:20px; font-weight:600;")
        layout.addWidget(title)
        hint = QLabel(
            "Deleted records are hidden from ledgers and dues until restored. "
            "Trashing a payment frees its amount from invoice allocations."
        )
        hint.setStyleSheet("color:#444; font-size:13px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_customers_tab(), "Customers")
        self.tabs.addTab(self._build_invoices_tab(), "Invoices")
        self.tabs.addTab(self._build_payments_tab(), "Payments")
        self.tabs.addTab(self._build_items_tab(), "Products")
        self.tabs.addTab(self._build_rm_tab(), "Raw materials")
        layout.addWidget(self.tabs, 1)

    def _build_customers_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.t_cust = QTableWidget(0, 3)
        self.t_cust.setHorizontalHeaderLabels(["Name", "Deleted at", ""])
        self.t_cust.verticalHeader().setVisible(False)
        v.addWidget(self.t_cust, 1)
        return w

    def _build_invoices_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.t_inv = QTableWidget(0, 5)
        self.t_inv.setHorizontalHeaderLabels(["Invoice", "Date", "Customer", "Amount", ""])
        self.t_inv.verticalHeader().setVisible(False)
        v.addWidget(self.t_inv, 1)
        return w

    def _build_payments_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.t_pay = QTableWidget(0, 5)
        self.t_pay.setHorizontalHeaderLabels(["Date", "Amount", "Customer", "Reference", ""])
        self.t_pay.verticalHeader().setVisible(False)
        v.addWidget(self.t_pay, 1)
        return w

    def _build_items_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.t_item = QTableWidget(0, 4)
        self.t_item.setHorizontalHeaderLabels(["Name", "HSN", "Deleted at", ""])
        self.t_item.verticalHeader().setVisible(False)
        v.addWidget(self.t_item, 1)
        return w

    def _build_rm_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.t_rm = QTableWidget(0, 3)
        self.t_rm.setHorizontalHeaderLabels(["RM code", "Deleted at", ""])
        self.t_rm.verticalHeader().setVisible(False)
        v.addWidget(self.t_rm, 1)
        return w

    def refresh(self) -> None:
        self._fill_cust()
        self._fill_inv()
        self._fill_pay()
        self._fill_item()
        self._fill_rm()

    def _fill_cust(self) -> None:
        rows = self._repo.list_deleted_customers()
        t = self.t_cust
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(r["name"] or "")))
            t.setItem(i, 1, QTableWidgetItem(str(r["deleted_at"] or "")))
            btn = QPushButton("Restore")
            bid = int(r["id"])
            btn.clicked.connect(lambda *, x=bid: self._restore_customer(x))
            row_w = QWidget()
            hl = QHBoxLayout(row_w)
            hl.setContentsMargins(2, 2, 2, 2)
            hl.addWidget(btn)
            t.setCellWidget(i, 2, row_w)

    def _fill_inv(self) -> None:
        rows = self._repo.list_deleted_invoices()
        t = self.t_inv
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(r["invoice_no"] or "")))
            t.setItem(i, 1, QTableWidgetItem(str(r["invoice_date"] or "")))
            t.setItem(i, 2, QTableWidgetItem(str(r["customer_name"] or "")))
            amt = r["total_after_tax"]
            t.setItem(i, 3, QTableWidgetItem(f"{float(amt):,.2f}" if amt is not None else ""))
            btn = QPushButton("Restore")
            bid = int(r["id"])
            btn.clicked.connect(lambda *, x=bid: self._restore_invoice(x))
            row_w = QWidget()
            hl = QHBoxLayout(row_w)
            hl.setContentsMargins(2, 2, 2, 2)
            hl.addWidget(btn)
            t.setCellWidget(i, 4, row_w)

    def _fill_pay(self) -> None:
        rows = self._repo.list_deleted_payments()
        t = self.t_pay
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(r["payment_date"] or "")))
            amt = r["amount"]
            t.setItem(i, 1, QTableWidgetItem(f"{float(amt):,.2f}" if amt is not None else ""))
            t.setItem(i, 2, QTableWidgetItem(str(r["customer_name"] or "")))
            t.setItem(i, 3, QTableWidgetItem(str(r["reference"] or "")))
            btn = QPushButton("Restore")
            bid = int(r["id"])
            btn.clicked.connect(lambda *, x=bid: self._restore_payment(x))
            row_w = QWidget()
            hl = QHBoxLayout(row_w)
            hl.setContentsMargins(2, 2, 2, 2)
            hl.addWidget(btn)
            t.setCellWidget(i, 4, row_w)

    def _fill_item(self) -> None:
        rows = self._repo.list_deleted_items()
        t = self.t_item
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(r["name"] or "")))
            t.setItem(i, 1, QTableWidgetItem(str(r["hsn"] or "")))
            t.setItem(i, 2, QTableWidgetItem(str(r["deleted_at"] or "")))
            btn = QPushButton("Restore")
            bid = int(r["id"])
            btn.clicked.connect(lambda *, x=bid: self._restore_item(x))
            row_w = QWidget()
            hl = QHBoxLayout(row_w)
            hl.setContentsMargins(2, 2, 2, 2)
            hl.addWidget(btn)
            t.setCellWidget(i, 3, row_w)

    def _fill_rm(self) -> None:
        rows = self._repo.list_deleted_raw_materials()
        t = self.t_rm
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(r["short_code"] or "")))
            t.setItem(i, 1, QTableWidgetItem(str(r["deleted_at"] or "")))
            btn = QPushButton("Restore")
            bid = int(r["id"])
            btn.clicked.connect(lambda *, x=bid: self._restore_raw_material(x))
            row_w = QWidget()
            hl = QHBoxLayout(row_w)
            hl.setContentsMargins(2, 2, 2, 2)
            hl.addWidget(btn)
            t.setCellWidget(i, 2, row_w)

    def _restore_customer(self, customer_id: int) -> None:
        try:
            with transaction(self._repo.conn):
                self._repo.restore_customer(customer_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.refresh()
        self.data_changed.emit()

    def _restore_invoice(self, invoice_id: int) -> None:
        try:
            with transaction(self._repo.conn):
                self._repo.restore_invoice(invoice_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.refresh()
        self.data_changed.emit()

    def _restore_payment(self, payment_id: int) -> None:
        try:
            with transaction(self._repo.conn):
                self._repo.restore_payment(payment_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.refresh()
        self.data_changed.emit()

    def _restore_item(self, item_id: int) -> None:
        try:
            with transaction(self._repo.conn):
                self._repo.restore_item(item_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.refresh()
        self.data_changed.emit()

    def _restore_raw_material(self, raw_material_id: int) -> None:
        try:
            with transaction(self._repo.conn):
                self._repo.restore_raw_material(raw_material_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.refresh()
        self.data_changed.emit()
