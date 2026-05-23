from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...db.conn import transaction
from ...repo import Repo
from ..page_header import make_page_header
from ..qt_icons import trash_icon_button_size, trash_row_icon
from ..theme import apply_primary_button


class PaymentsPage(QWidget):
    data_changed = Signal()

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(scroll, 1)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        scroll.setWidget(inner)

        layout.addWidget(
            make_page_header(
                "Payments",
                "Record receipts; amounts auto-allocate FIFO to the oldest open invoices per customer.",
            )
        )

        card = QFrame()
        card.setObjectName("formCard")
        card_layout = QFormLayout(card)

        self.customer_cb = QComboBox()
        self.customer_cb.setMinimumHeight(32)
        card_layout.addRow("Customer", self.customer_cb)

        self.date_inp = QLineEdit()
        self.date_inp.setPlaceholderText("YYYY-MM-DD")
        self.date_inp.setText(date.today().isoformat())
        self.date_inp.setMinimumHeight(32)
        card_layout.addRow("Payment date", self.date_inp)

        self.amount_inp = QLineEdit()
        self.amount_inp.setPlaceholderText("e.g. 15000")
        self.amount_inp.setMinimumHeight(32)
        card_layout.addRow("Amount", self.amount_inp)

        self.mode_cb = QComboBox()
        self.mode_cb.addItems(["Bank", "UPI", "Cash", "Cheque", "Other"])
        self.mode_cb.setMinimumHeight(32)
        card_layout.addRow("Mode", self.mode_cb)

        self.ref_inp = QLineEdit()
        self.ref_inp.setPlaceholderText("Reference / UTR / note")
        self.ref_inp.setMinimumHeight(32)
        card_layout.addRow("Reference", self.ref_inp)

        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("Save Payment (Auto-Allocate FIFO)")
        self.save_btn.setMinimumHeight(38)
        apply_primary_button(self.save_btn)
        btn_row.addWidget(self.save_btn)
        btn_row.addStretch(1)
        card_layout.addRow(btn_row)

        layout.addWidget(card)

        layout.addWidget(QLabel("Recent payments"))
        self.pay_table = QTableWidget(0, 5)
        self.pay_table.setHorizontalHeaderLabels(["Date", "Customer", "Amount", "Reference", ""])
        self.pay_table.verticalHeader().setVisible(False)
        self.pay_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pay_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pay_table.setSelectionMode(QTableWidget.SingleSelection)
        self.pay_table.setStyleSheet("QTableWidget{font-size:13px;}")
        self.pay_table.setMinimumHeight(280)
        layout.addWidget(self.pay_table)

        trash_row = QHBoxLayout()
        self.btn_trash_pay = QPushButton("Move selected payment to trash")
        self.btn_trash_pay.setMinimumHeight(32)
        self.btn_trash_pay.clicked.connect(self._trash_selected_payment)
        trash_row.addWidget(self.btn_trash_pay)
        trash_row.addStretch(1)
        layout.addLayout(trash_row)
        layout.addStretch(1)

        self.save_btn.clicked.connect(self._save_payment)
        self.reload_customers()
        self.reload_recent_payments()

    def reload_customers(self) -> None:
        self.customer_cb.clear()
        customers = self._repo.list_customers()
        for c in customers:
            self.customer_cb.addItem(str(c["name"]), int(c["id"]))

    def focus_new_payment(self) -> None:
        self.reload_customers()
        self.amount_inp.setFocus()

    def reload_recent_payments(self) -> None:
        rows = self._repo.list_payments_recent(100)
        trash_ico = trash_row_icon()
        isz = trash_icon_button_size()
        self.pay_table.setUpdatesEnabled(False)
        self.pay_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            pid = int(r["id"])
            it0 = QTableWidgetItem(str(r["payment_date"] or ""))
            it0.setData(Qt.UserRole, pid)
            self.pay_table.setItem(i, 0, it0)
            self.pay_table.setItem(i, 1, QTableWidgetItem(str(r["customer_name"] or "")))
            amt = r["amount"]
            self.pay_table.setItem(i, 2, QTableWidgetItem(f"{float(amt):,.2f}" if amt is not None else ""))
            self.pay_table.setItem(i, 3, QTableWidgetItem(str(r["reference"] or "")))
            btn = QPushButton()
            btn.setIcon(trash_ico)
            btn.setIconSize(isz)
            btn.setToolTip("Move to trash")
            btn.setFlat(True)
            btn.setFixedSize(32, 28)
            btn.clicked.connect(lambda checked=False, x=pid: self._trash_payment_id(x))
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(2, 2, 2, 2)
            hl.addWidget(btn)
            self.pay_table.setCellWidget(i, 4, w)
        self.pay_table.setUpdatesEnabled(True)

    def _trash_payment_id(self, payment_id: int) -> None:
        if (
            QMessageBox.question(
                self,
                "Confirm",
                "Move this payment to trash? Allocations to invoices will be ignored until the payment is restored.",
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
        self.reload_recent_payments()
        self.data_changed.emit()

    def _trash_selected_payment(self) -> None:
        r = self.pay_table.currentRow()
        if r < 0:
            QMessageBox.information(self, "Payments", "Select a row in Recent payments.")
            return
        it = self.pay_table.item(r, 0)
        if it is None:
            return
        pid = it.data(Qt.UserRole)
        if pid is None:
            return
        self._trash_payment_id(int(pid))

    def _save_payment(self) -> None:
        if self.customer_cb.currentIndex() < 0:
            QMessageBox.warning(self, "Missing", "Please add a customer first (Setup → Seed Data).")
            return

        try:
            customer_id = int(self.customer_cb.currentData())
            payment_date = date.fromisoformat(self.date_inp.text().strip())
            amount = float(self.amount_inp.text().strip())
            mode = self.mode_cb.currentText()
            ref = self.ref_inp.text().strip()
        except Exception:
            QMessageBox.warning(self, "Invalid", "Please check date (YYYY-MM-DD) and amount.")
            return

        try:
            with transaction(self._repo.conn):
                self._repo.create_payment(
                    customer_id=customer_id,
                    payment_date=payment_date,
                    amount=amount,
                    mode=mode,
                    reference=ref,
                )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self.amount_inp.clear()
        self.ref_inp.clear()
        QMessageBox.information(self, "Saved", "Payment saved and allocated to oldest unpaid invoices.")
        self.reload_recent_payments()
        self.data_changed.emit()

