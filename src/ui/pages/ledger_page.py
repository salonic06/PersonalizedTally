from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from ...db.conn import transaction
from ...open_file import open_local_file
from ...repo import Repo
from ..page_header import make_page_header
from ..table_action import configure_action_column, make_trash_cell, polish_data_table
from ..table_empty import clear_table_body_for_fill, set_table_empty_state
from ...safe_delete import delete_invoice_excel_if_allowed
from ..trash_invoice_dialog import (
    TrashInvoiceChoice,
    confirm_invoice_permanent_delete,
    confirm_trash_invoice,
)


class LedgerPage(QWidget):
    data_changed = Signal()

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo

        layout = QVBoxLayout(self)
        layout.addWidget(
            make_page_header(
                "Customer Ledger",
                "Running balance for one customer — invoices increase balance, payments reduce it.",
            )
        )

        pick_row = QHBoxLayout()
        pick_row.addWidget(QLabel("Customer"))
        self.customer_cb = QComboBox()
        self.customer_cb.setMinimumHeight(32)
        pick_row.addWidget(self.customer_cb, 1)
        layout.addLayout(pick_row)

        range_row = QHBoxLayout()
        self.entry_range_cb = QCheckBox("Filter by entry date (default: last 3 months)")
        self.entry_range_cb.setChecked(True)
        range_row.addWidget(self.entry_range_cb)
        range_row.addWidget(QLabel("From"))
        self.entry_from_de = QDateEdit()
        self.entry_from_de.setCalendarPopup(True)
        self.entry_from_de.setDisplayFormat("dd-MM-yyyy")
        self.entry_from_de.setDate(QDate.currentDate().addMonths(-3))
        self.entry_from_de.setEnabled(True)
        self.entry_from_de.setMinimumHeight(32)
        range_row.addWidget(self.entry_from_de)
        range_row.addWidget(QLabel("to"))
        self.entry_to_de = QDateEdit()
        self.entry_to_de.setCalendarPopup(True)
        self.entry_to_de.setDisplayFormat("dd-MM-yyyy")
        self.entry_to_de.setDate(QDate.currentDate())
        self.entry_to_de.setEnabled(True)
        self.entry_to_de.setMinimumHeight(32)
        range_row.addWidget(self.entry_to_de)
        range_row.addStretch(1)
        layout.addLayout(range_row)

        self.entry_range_cb.toggled.connect(self._on_entry_range_toggled)
        self.entry_from_de.dateChanged.connect(self.refresh)
        self.entry_to_de.dateChanged.connect(self.refresh)

        self.summary = QLabel("")
        self.summary.setStyleSheet("color:#333; font-size:13px;")
        layout.addWidget(self.summary)

        act = QHBoxLayout()
        self.btn_open_xl = QPushButton("Open invoice Excel")
        self.btn_open_xl.setMinimumHeight(32)
        self.btn_open_xl.setEnabled(False)
        self.btn_open_xl.clicked.connect(self._open_selected_invoice_excel)
        act.addWidget(self.btn_open_xl)
        act.addStretch(1)
        layout.addLayout(act)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["Date", "Type", "Reference", "Debit", "Credit", "Balance", ""]
        )
        self.table.setAlternatingRowColors(True)
        polish_data_table(self.table)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_sel)
        self.table.itemDoubleClicked.connect(self._on_double)
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        # Reference is content-sized (capped); Balance stretches so the row doesn’t leave a huge gap.
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)
        configure_action_column(self.table, 6)
        layout.addWidget(self.table, 1)

        self.customer_cb.currentIndexChanged.connect(self.refresh)
        self.reload_customers()

    def set_customer_id(self, customer_id: int) -> None:
        idx = self.customer_cb.findData(customer_id)
        if idx >= 0:
            self.customer_cb.setCurrentIndex(idx)
        self.refresh()

    def _on_sel(self) -> None:
        inv_id, path = self._selected_invoice_meta()
        self.btn_open_xl.setEnabled(bool(path and str(path).strip()))

    def _selected_invoice_meta(self) -> tuple[int | None, str | None]:
        r = self.table.currentRow()
        if r < 0:
            return None, None
        it = self.table.item(r, 0)
        if it is None:
            return None, None
        typ_it = self.table.item(r, 1)
        if typ_it is None or typ_it.text() != "INVOICE":
            return None, None
        iid = it.data(Qt.UserRole)
        path = it.data(Qt.UserRole + 1)
        return (int(iid) if iid is not None else None), (str(path).strip() if path else None) or None

    def _on_double(self, item: QTableWidgetItem) -> None:
        if item.column() != 0:
            return
        r = item.row()
        typ = self.table.item(r, 1)
        if typ is None or typ.text() != "INVOICE":
            return
        path = item.data(Qt.UserRole + 1)
        if not path or not str(path).strip():
            return
        ok, err = open_local_file(str(path))
        if not ok:
            QMessageBox.warning(self, "Open file", err)

    def _open_selected_invoice_excel(self) -> None:
        _, path = self._selected_invoice_meta()
        if not path:
            QMessageBox.information(self, "Excel", "No file path for this row.")
            return
        ok, err = open_local_file(path)
        if not ok:
            QMessageBox.warning(self, "Open file", err)

    def _trash_invoice_by_id(self, invoice_id: int) -> None:
        xp = self._repo.get_invoice_excel_path(invoice_id)
        path = str(xp).strip() if xp else ""
        has_xl = bool(path)
        choice = confirm_trash_invoice(self, has_excel_path=has_xl)
        if choice == TrashInvoiceChoice.CANCEL:
            return

        if choice == TrashInvoiceChoice.DB_ONLY:
            try:
                with transaction(self._repo.conn):
                    self._repo.soft_delete_invoice(invoice_id)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
        else:
            inv_no = self._repo.get_invoice_no(invoice_id) or ""
            if not confirm_invoice_permanent_delete(self, inv_no):
                return
            try:
                with transaction(self._repo.conn):
                    self._repo.permanently_delete_invoice(invoice_id)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            out = self._repo.get_setting("invoice_output_folder", "")
            ok, err = delete_invoice_excel_if_allowed(path, out)
            if path and (not ok) and err:
                QMessageBox.warning(
                    self,
                    "Excel file",
                    "The invoice was removed from the database, but the Excel file could not be deleted:\n"
                    + err,
                )

        self.refresh()
        self.data_changed.emit()

    def _trash_payment_by_id(self, payment_id: int) -> None:
        if (
            QMessageBox.question(
                self,
                "Confirm",
                "Move this payment to trash? Allocations to invoices are ignored until the payment is restored.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            with transaction(self._repo.conn):
                self._repo.soft_delete_payment(payment_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.refresh()
        self.data_changed.emit()

    def _on_entry_range_toggled(self, on: bool) -> None:
        self.entry_from_de.setEnabled(on)
        self.entry_to_de.setEnabled(on)
        self.refresh()

    def _entry_bounds(self) -> tuple[date | None, date | None]:
        if not self.entry_range_cb.isChecked():
            return None, None
        a = self.entry_from_de.date().toPython()
        b = self.entry_to_de.date().toPython()
        if a <= b:
            return a, b
        return b, a

    def reload_customers(self) -> None:
        current_id = self.customer_cb.currentData()
        self.customer_cb.clear()
        for c in self._repo.list_customers():
            self.customer_cb.addItem(str(c["name"]), int(c["id"]))
        if current_id is not None:
            idx = self.customer_cb.findData(current_id)
            if idx >= 0:
                self.customer_cb.setCurrentIndex(idx)

    def refresh(self) -> None:
        if self.customer_cb.currentIndex() < 0:
            set_table_empty_state(self.table, "No customers yet — add customers under Setup (Seed Data).")
            self.summary.setText("No customers yet.")
            return

        customer_id = int(self.customer_cb.currentData())
        ef, et = self._entry_bounds()
        rows = self._repo.ledger_rows(customer_id, entry_from=ef, entry_to=et)
        if not rows:
            if self.entry_range_cb.isChecked():
                set_table_empty_state(
                    self.table, "No ledger entries in the selected date range."
                )
            else:
                set_table_empty_state(
                    self.table,
                    "No invoices or payments for this customer yet.",
                )
            self.summary.setText(self.customer_cb.currentText())
            self._on_sel()
            return

        self.table.setUpdatesEnabled(False)
        clear_table_body_for_fill(self.table)
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            items = [
                QTableWidgetItem(r.entry_date.strftime("%d-%m-%Y")),
                QTableWidgetItem(r.entry_type),
                QTableWidgetItem(r.ref),
                QTableWidgetItem(f"{r.debit:,.2f}"),
                QTableWidgetItem(f"{r.credit:,.2f}"),
                QTableWidgetItem(f"{r.balance:,.2f}"),
            ]
            if r.entry_type == "INVOICE" and r.invoice_id is not None:
                items[0].setData(Qt.UserRole, r.invoice_id)
                items[0].setData(Qt.UserRole + 1, r.excel_path or "")
            for col, it in enumerate(items):
                if col in (3, 4, 5):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, col, it)

            enabled = (r.entry_type == "INVOICE" and r.invoice_id is not None) or (
                r.entry_type == "PAYMENT" and r.payment_id is not None
            )
            if r.entry_type == "INVOICE" and r.invoice_id is not None:
                iid = int(r.invoice_id)
                on_del = lambda x=iid: self._trash_invoice_by_id(x)
            elif r.entry_type == "PAYMENT" and r.payment_id is not None:
                pid = int(r.payment_id)
                on_del = lambda x=pid: self._trash_payment_by_id(x)
            else:
                on_del = lambda: None
            self.table.setCellWidget(
                i,
                6,
                make_trash_cell(on_del, tooltip="Move to trash", enabled=enabled),
            )

        self.table.setUpdatesEnabled(True)
        self.table.resizeColumnToContents(2)
        ref_w = self.table.columnWidth(2)
        if ref_w > 220:
            self.table.setColumnWidth(2, 220)
        self._on_sel()

        opening = 0.0
        if ef is not None:
            if rows:
                opening = rows[0].balance - rows[0].debit + rows[0].credit
            else:
                opening = self._repo.ledger_net_before(customer_id, ef)
        closing = rows[-1].balance if rows else opening

        if ef is None and et is None:
            self.summary.setText(
                f"Entries: {len(rows)}  |  Current balance (Debit-Credit): {closing:,.2f}"
            )
        else:
            span = f"{ef.strftime('%d-%m-%Y')}–{et.strftime('%d-%m-%Y')}" if ef and et else ""
            parts = [f"Entries: {len(rows)}"]
            if span:
                parts.append(span)
            if ef is not None:
                parts.append(f"Brought forward: {opening:,.2f}")
            parts.append(f"Closing: {closing:,.2f}")
            self.summary.setText("  |  ".join(parts))
