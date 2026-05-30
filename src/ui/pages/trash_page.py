from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
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
from ..page_header import make_page_header
from ..table_action import configure_action_column, make_restore_cell, polish_data_table
from ..table_empty import clear_table_body_for_fill, set_table_empty_state


class TrashPage(QWidget):
    """Restore soft-deleted customers, invoices, payments, and products."""

    data_changed = Signal()

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo

        layout = QVBoxLayout(self)
        layout.addWidget(
            make_page_header(
                "Trash",
                "Restore soft-deleted customers, invoices, payments, and products.",
            )
        )

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
        polish_data_table(self.t_cust)
        configure_action_column(self.t_cust, 2)
        v.addWidget(self.t_cust, 1)
        return w

    def _build_invoices_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.t_inv = QTableWidget(0, 5)
        self.t_inv.setHorizontalHeaderLabels(["Invoice", "Date", "Customer", "Amount", ""])
        polish_data_table(self.t_inv)
        configure_action_column(self.t_inv, 4)
        v.addWidget(self.t_inv, 1)
        return w

    def _build_payments_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.t_pay = QTableWidget(0, 5)
        self.t_pay.setHorizontalHeaderLabels(["Date", "Amount", "Customer", "Reference", ""])
        polish_data_table(self.t_pay)
        configure_action_column(self.t_pay, 4)
        v.addWidget(self.t_pay, 1)
        return w

    def _build_items_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.t_item = QTableWidget(0, 4)
        self.t_item.setHorizontalHeaderLabels(["Name", "HSN", "Deleted at", ""])
        polish_data_table(self.t_item)
        configure_action_column(self.t_item, 3)
        v.addWidget(self.t_item, 1)
        return w

    def _build_rm_tab(self) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        self.t_rm = QTableWidget(0, 3)
        self.t_rm.setHorizontalHeaderLabels(["RM code", "Deleted at", ""])
        polish_data_table(self.t_rm)
        configure_action_column(self.t_rm, 2)
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
        if not rows:
            set_table_empty_state(t, "Trash is empty — no deleted customers.")
            return
        clear_table_body_for_fill(t)
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(r["name"] or "")))
            t.setItem(i, 1, QTableWidgetItem(str(r["deleted_at"] or "")))
            bid = int(r["id"])
            t.setCellWidget(i, 2, make_restore_cell(lambda *, x=bid: self._restore_customer(x)))

    def _fill_inv(self) -> None:
        rows = self._repo.list_deleted_invoices()
        t = self.t_inv
        if not rows:
            set_table_empty_state(t, "No deleted invoices in trash.")
            return
        clear_table_body_for_fill(t)
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(r["invoice_no"] or "")))
            t.setItem(i, 1, QTableWidgetItem(str(r["invoice_date"] or "")))
            t.setItem(i, 2, QTableWidgetItem(str(r["customer_name"] or "")))
            amt = r["total_after_tax"]
            t.setItem(i, 3, QTableWidgetItem(f"{float(amt):,.2f}" if amt is not None else ""))
            bid = int(r["id"])
            t.setCellWidget(i, 4, make_restore_cell(lambda *, x=bid: self._restore_invoice(x)))

    def _fill_pay(self) -> None:
        rows = self._repo.list_deleted_payments()
        t = self.t_pay
        if not rows:
            set_table_empty_state(t, "No deleted payments in trash.")
            return
        clear_table_body_for_fill(t)
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(r["payment_date"] or "")))
            amt = r["amount"]
            t.setItem(i, 1, QTableWidgetItem(f"{float(amt):,.2f}" if amt is not None else ""))
            t.setItem(i, 2, QTableWidgetItem(str(r["customer_name"] or "")))
            t.setItem(i, 3, QTableWidgetItem(str(r["reference"] or "")))
            bid = int(r["id"])
            t.setCellWidget(i, 4, make_restore_cell(lambda *, x=bid: self._restore_payment(x)))

    def _fill_item(self) -> None:
        rows = self._repo.list_deleted_items()
        t = self.t_item
        if not rows:
            set_table_empty_state(t, "No deleted products in trash.")
            return
        clear_table_body_for_fill(t)
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(r["name"] or "")))
            t.setItem(i, 1, QTableWidgetItem(str(r["hsn"] or "")))
            t.setItem(i, 2, QTableWidgetItem(str(r["deleted_at"] or "")))
            bid = int(r["id"])
            t.setCellWidget(i, 3, make_restore_cell(lambda *, x=bid: self._restore_item(x)))

    def _fill_rm(self) -> None:
        rows = self._repo.list_deleted_raw_materials()
        t = self.t_rm
        if not rows:
            set_table_empty_state(t, "No deleted raw materials in trash.")
            return
        clear_table_body_for_fill(t)
        t.setRowCount(len(rows))
        for i, r in enumerate(rows):
            t.setItem(i, 0, QTableWidgetItem(str(r["short_code"] or "")))
            t.setItem(i, 1, QTableWidgetItem(str(r["deleted_at"] or "")))
            bid = int(r["id"])
            t.setCellWidget(i, 2, make_restore_cell(lambda *, x=bid: self._restore_raw_material(x)))

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
