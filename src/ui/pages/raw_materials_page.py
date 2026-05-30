from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
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
from ..form_util import configure_form, form_add_row
from ..page_header import make_page_header
from ..table_action import (
    configure_action_column,
    make_text_action_cell,
    make_trash_cell,
    polish_data_table,
)
from ..table_empty import clear_table_body_for_fill, set_table_empty_state
from ..theme import is_dark_mode_enabled


class RawMaterialsPage(QWidget):
    """Stock operations: balances, receive, lots. Edit RM master in Setup (Seed Data)."""

    data_changed = Signal()

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo
        self._pending_rm_focus: int | None = None

        root = QVBoxLayout(self)
        root.addWidget(
            make_page_header(
                "Raw materials & stock",
                "Receive lots into stock, view balances, and manage lot codes (CODE-DDMMYY-N).",
            )
        )

        tabs = QTabWidget()
        root.addWidget(tabs, 1)

        # --- Single RM list (codes only) ---
        self._tab_stock = QWidget()
        stock_lay = QVBoxLayout(self._tab_stock)
        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setMinimumHeight(34)
        bar.addWidget(self.btn_refresh)
        bar.addWidget(QLabel("Type"))
        self.bal_type_filter_cb = QComboBox()
        self.bal_type_filter_cb.setMinimumHeight(32)
        self.bal_type_filter_cb.setMinimumWidth(160)
        self.bal_type_filter_cb.setToolTip("Filter the RM list by category (same field as Seed Data → Type).")
        bar.addWidget(self.bal_type_filter_cb)
        bar.addStretch(1)
        stock_lay.addLayout(bar)
        self.tbl_bal = QTableWidget(0, 6)
        self.tbl_bal.setHorizontalHeaderLabels(
            ["RM code", "Type", "Unit", "On hand", "Reorder", ""]
        )
        bh = self.tbl_bal.horizontalHeader()
        bh.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        bh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        for c in (2, 3, 4, 5):
            bh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        self.tbl_bal.setAlternatingRowColors(False)
        polish_data_table(self.tbl_bal)
        configure_action_column(self.tbl_bal, 5)
        self.tbl_bal.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_bal.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        stock_lay.addWidget(self.tbl_bal, 1)
        tabs.addTab(self._tab_stock, "RM list")

        # --- Receive ---
        self._tab_recv = QWidget()
        recv_lay = QVBoxLayout(self._tab_recv)
        form = QFormLayout()
        configure_form(form)
        self.recv_rm_cb = QComboBox()
        self.recv_rm_cb.setMinimumHeight(32)
        form_add_row(form, "RM code", self.recv_rm_cb)
        self.recv_date = QDateEdit()
        self.recv_date.setCalendarPopup(True)
        self.recv_date.setDisplayFormat("dd-MM-yyyy")
        t = date.today()
        self.recv_date.setDate(QDate(t.year, t.month, t.day))
        self.recv_date.setMinimumHeight(32)
        form_add_row(form, "Received date", self.recv_date)
        self.recv_qty = QDoubleSpinBox()
        self.recv_qty.setDecimals(2)
        self.recv_qty.setMaximum(1e12)
        self.recv_qty.setMinimum(0.01)
        self.recv_qty.setValue(1.0)
        self.recv_qty.setMinimumHeight(32)
        form_add_row(form, "Quantity", self.recv_qty)
        self.recv_cost = QDoubleSpinBox()
        self.recv_cost.setDecimals(2)
        self.recv_cost.setMaximum(1e12)
        self.recv_cost.setMinimum(0.0)
        self.recv_cost.setMinimumHeight(32)
        form_add_row(form, "Unit cost (₹ / unit)", self.recv_cost)
        self.recv_supplier = QLineEdit()
        self.recv_supplier.setMinimumHeight(32)
        self.recv_supplier.setPlaceholderText("Supplier batch / COA ref (optional)")
        self.recv_supplier.setToolTip(
            "Supplier’s batch or certificate reference — for traceability with the vendor (shown in lot ledger)."
        )
        form_add_row(form, "Supplier ref", self.recv_supplier)
        self.recv_notes = QLineEdit()
        self.recv_notes.setMinimumHeight(32)
        self.recv_notes.setPlaceholderText("Optional memo for this receipt (shown in lot ledger Notes)")
        self.recv_notes.setToolTip(
            "Your own note for this receipt (e.g. GRN, vehicle, remarks). Stored on the lot and shown in the ledger."
        )
        form_add_row(form, "Notes", self.recv_notes)
        recv_lay.addLayout(form)
        self.lbl_next_code = QLabel("Next lot code: —")
        self.lbl_next_code.setStyleSheet("font-weight:600;")
        recv_lay.addWidget(self.lbl_next_code)
        self.btn_save_lot = QPushButton("Receive into stock")
        self.btn_save_lot.setMinimumHeight(40)
        recv_lay.addWidget(self.btn_save_lot)
        recv_lay.addStretch(1)
        tabs.addTab(self._tab_recv, "Receive stock")

        # --- Lots ---
        self._tab_lots = QWidget()
        lots_lay = QVBoxLayout(self._tab_lots)
        flt = QHBoxLayout()
        flt.addWidget(QLabel("RM code"))
        self.lots_filter_cb = QComboBox()
        self.lots_filter_cb.setMinimumHeight(32)
        flt.addWidget(self.lots_filter_cb, 1)
        lots_lay.addLayout(flt)
        lot_legend = QLabel(
            "Supplier ref: vendor batch / COA id. Notes: your memo from Receive stock (GRN, remarks, etc.)."
        )
        lot_legend.setStyleSheet("color:#555; font-size:12px;")
        lot_legend.setWordWrap(True)
        lots_lay.addWidget(lot_legend)
        self.tbl_lots = QTableWidget(0, 10)
        self.tbl_lots.setHorizontalHeaderLabels(
            [
                "Lot code",
                "RM code",
                "Date",
                "Received",
                "Remaining",
                "Unit",
                "₹/unit",
                "Supplier ref",
                "Notes",
                "",
            ]
        )
        lh = self.tbl_lots.horizontalHeader()
        lh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        lh.setMinimumSectionSize(72)
        lh.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        lh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for c in (3, 4, 5, 6, 7):
            lh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        lh.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        lh.setSectionResizeMode(9, QHeaderView.ResizeMode.Fixed)
        lh.resizeSection(9, 44)
        self.tbl_lots.setAlternatingRowColors(False)
        polish_data_table(self.tbl_lots)
        configure_action_column(self.tbl_lots, 9)
        self.tbl_lots.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lots_lay.addWidget(self.tbl_lots, 1)
        tabs.addTab(self._tab_lots, "Lot ledger")

        self.btn_refresh.clicked.connect(self.refresh_all)
        self.bal_type_filter_cb.currentIndexChanged.connect(self._reload_balance_table)
        self.btn_save_lot.clicked.connect(self._receive_lot)
        self.recv_rm_cb.currentIndexChanged.connect(self._update_next_lot_preview)
        self.recv_date.dateChanged.connect(lambda *_: self._update_next_lot_preview())
        self.lots_filter_cb.currentIndexChanged.connect(self._reload_lots_table)

        self.tbl_bal.cellClicked.connect(self._on_balance_cell)

        self.refresh_all()

    def refresh_all(self) -> None:
        self._reload_balance_type_filter_combo()
        self._reload_balance_table()
        self._reload_rm_combos()
        self._update_next_lot_preview()
        self._reload_lots_table()
        if self._pending_rm_focus is not None:
            rid = self._pending_rm_focus
            self._pending_rm_focus = None
            idx = self.recv_rm_cb.findData(rid)
            if idx >= 0:
                self.recv_rm_cb.setCurrentIndex(idx)
            idx2 = self.lots_filter_cb.findData(rid)
            if idx2 >= 0:
                self.lots_filter_cb.setCurrentIndex(idx2)

    def focus_raw_material(self, raw_material_id: int) -> None:
        self._pending_rm_focus = raw_material_id
        self.refresh_all()

    def _reload_balance_type_filter_combo(self) -> None:
        preserve = self.bal_type_filter_cb.currentData()
        self.bal_type_filter_cb.blockSignals(True)
        self.bal_type_filter_cb.clear()
        self.bal_type_filter_cb.addItem("All types", None)
        for t in self._repo.list_distinct_rm_types():
            self.bal_type_filter_cb.addItem(t, t)
        self.bal_type_filter_cb.blockSignals(False)
        if preserve is not None:
            ix = self.bal_type_filter_cb.findData(preserve)
            if ix >= 0:
                self.bal_type_filter_cb.setCurrentIndex(ix)
                return
        self.bal_type_filter_cb.setCurrentIndex(0)

    def _reload_rm_combos(self) -> None:
        rows = self._repo.list_raw_materials()
        self.recv_rm_cb.blockSignals(True)
        self.recv_rm_cb.clear()
        for r in rows:
            self.recv_rm_cb.addItem(str(r["short_code"]), int(r["id"]))
        self.recv_rm_cb.blockSignals(False)

        self.lots_filter_cb.blockSignals(True)
        self.lots_filter_cb.clear()
        self.lots_filter_cb.addItem("All", None)
        for r in rows:
            self.lots_filter_cb.addItem(str(r["short_code"]), int(r["id"]))
        self.lots_filter_cb.blockSignals(False)

    def _reload_balance_table(self) -> None:
        rows = self._repo.list_raw_material_balances()
        sel = self.bal_type_filter_cb.currentData()
        if sel is not None:
            st = str(sel).strip()
            rows = [
                r
                for r in rows
                if r["rm_type"] is not None and str(r["rm_type"]).strip() == st
            ]
        if not rows:
            set_table_empty_state(
                self.tbl_bal,
                "No raw materials yet — add them under Setup (Seed Data).",
            )
            return
        clear_table_body_for_fill(self.tbl_bal)
        self.tbl_bal.setRowCount(len(rows))
        dark = is_dark_mode_enabled(self._repo)
        warn_bg = QBrush(QColor("#4c0519" if dark else "#fff7ed"))
        warn_fg = QBrush(QColor("#fde68a" if dark else "#9a3412"))
        for i, r in enumerate(rows):
            rid = int(r["raw_material_id"])
            on_hand = float(r["on_hand"])
            typ = r["rm_type"]
            typ_s = str(typ) if typ else "—"
            code_it = QTableWidgetItem(str(r["short_code"]))
            code_it.setData(Qt.ItemDataRole.UserRole, rid)
            self.tbl_bal.setItem(i, 0, code_it)
            self.tbl_bal.setItem(i, 1, QTableWidgetItem(typ_s))
            self.tbl_bal.setItem(i, 2, QTableWidgetItem(str(r["unit"] or "")))
            oh = QTableWidgetItem(f"{on_hand:,.2f}")
            oh.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_bal.setItem(i, 3, oh)
            rl = r["reorder_level"]
            rl_s = f"{float(rl):,.2f}" if rl is not None else "—"
            rlit = QTableWidgetItem(rl_s)
            rlit.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_bal.setItem(i, 4, rlit)
            below_reorder = (
                rl is not None and float(rl) > 0 and on_hand < float(rl) - 1e-9
            )
            for c in range(5):
                it = self.tbl_bal.item(i, c)
                if it is not None:
                    if below_reorder:
                        it.setBackground(warn_bg)
                        it.setForeground(warn_fg)
                    else:
                        it.setData(Qt.ItemDataRole.BackgroundRole, None)
                        it.setData(Qt.ItemDataRole.ForegroundRole, None)
            if below_reorder:
                oh.setToolTip(f"On hand is below reorder level ({rl_s}).")
                rlit.setToolTip("Reorder level for this RM.")
            self.tbl_bal.setCellWidget(
                i,
                5,
                make_text_action_cell(
                    "Remove",
                    lambda *, x=rid: self._trash_raw_material(x),
                    enabled=on_hand <= 0.00001,
                ),
            )

    def _on_balance_cell(self, row: int, col: int) -> None:
        if col == 5:
            return
        it = self.tbl_bal.item(row, 0)
        if it is None:
            return
        rid = it.data(Qt.ItemDataRole.UserRole)
        if rid is not None:
            self.focus_raw_material(int(rid))

    def _update_next_lot_preview(self) -> None:
        iid = self.recv_rm_cb.currentData()
        if iid is None:
            self.lbl_next_code.setText("Next lot code: —")
            self.btn_save_lot.setEnabled(False)
            return
        qd = self.recv_date.date()
        rd = date(qd.year(), qd.month(), qd.day())
        try:
            code = self._repo.peek_next_lot_code(int(iid), rd)
            self.lbl_next_code.setText(f"Next lot code: {code}")
            self.btn_save_lot.setEnabled(True)
        except Exception as e:
            self.lbl_next_code.setText(f"Next lot code: — ({e})")
            self.btn_save_lot.setEnabled(False)

    def _receive_lot(self) -> None:
        iid = self.recv_rm_cb.currentData()
        if iid is None:
            QMessageBox.information(
                self,
                "RM list",
                "No raw materials yet. Add them under Setup (Seed Data) → Raw materials master.",
            )
            return
        d = self.recv_date.date()
        rd = date(d.year(), d.month(), d.day())
        qty = float(self.recv_qty.value())
        cost = float(self.recv_cost.value())
        if qty <= 0:
            QMessageBox.warning(self, "Invalid", "Quantity must be > 0.")
            return
        try:
            with transaction(self._repo.conn):
                _, lot_code = self._repo.receive_rm_stock_lot(
                    int(iid),
                    rd,
                    qty,
                    cost,
                    supplier_ref=self.recv_supplier.text(),
                    notes=self.recv_notes.text(),
                )
        except Exception as e:
            QMessageBox.warning(self, "Save failed", str(e))
            return
        QMessageBox.information(self, "Received", f"Saved lot {lot_code}")
        self.recv_supplier.clear()
        self.recv_notes.clear()
        self.refresh_all()
        self.data_changed.emit()

    def _reload_lots_table(self) -> None:
        fid = self.lots_filter_cb.currentData()
        rid = int(fid) if fid is not None else None
        rows = self._repo.list_rm_stock_lots(raw_material_id=rid)
        if not rows:
            if rid is not None:
                set_table_empty_state(self.tbl_lots, "No stock lots for this raw material yet.")
            else:
                set_table_empty_state(self.tbl_lots, "No stock lots received yet.")
            return
        clear_table_body_for_fill(self.tbl_lots)
        self.tbl_lots.setRowCount(len(rows))
        for i, r in enumerate(rows):
            lid = int(r["id"])
            self.tbl_lots.setItem(i, 0, QTableWidgetItem(str(r["lot_code"])))
            self.tbl_lots.setItem(i, 1, QTableWidgetItem(str(r["rm_code"])))
            self.tbl_lots.setItem(i, 2, QTableWidgetItem(str(r["received_date"])))
            qr = float(r["qty_received"])
            qm = float(r["qty_remaining"])
            a = QTableWidgetItem(f"{qr:,.2f}")
            a.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_lots.setItem(i, 3, a)
            b = QTableWidgetItem(f"{qm:,.2f}")
            b.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_lots.setItem(i, 4, b)
            self.tbl_lots.setItem(i, 5, QTableWidgetItem(str(r["unit"] or "")))
            uc = float(r["unit_cost"])
            c = QTableWidgetItem(f"{uc:,.2f}")
            c.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_lots.setItem(i, 6, c)
            self.tbl_lots.setItem(i, 7, QTableWidgetItem(str(r["supplier_ref"] or "")))
            note_s = str(r["notes"] or "").strip()
            nit = QTableWidgetItem(note_s)
            if len(note_s) > 80:
                nit.setToolTip(note_s)
            self.tbl_lots.setItem(i, 8, nit)
            self.tbl_lots.setCellWidget(
                i,
                9,
                make_trash_cell(
                    lambda x=lid: self._delete_lot(x),
                    tooltip="Remove lot from ledger",
                ),
            )

    def _delete_lot(self, lot_id: int) -> None:
        if (
            QMessageBox.question(
                self,
                "Remove lot",
                "Permanently delete this lot from the database (not recoverable from Trash)? "
                "On-hand stock will drop by this lot’s remaining quantity.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            with transaction(self._repo.conn):
                self._repo.delete_rm_stock_lot(lot_id)
        except Exception as e:
            QMessageBox.warning(self, "Remove failed", str(e))
            return
        self.refresh_all()
        self.data_changed.emit()

    def _trash_raw_material(self, raw_material_id: int) -> None:
        row = self._repo.get_raw_material(raw_material_id)
        code = str(row["short_code"]) if row else "?"
        if (
            QMessageBox.question(
                self,
                "Remove",
                f"Remove RM code “{code}” from the active list? (Only when on-hand stock is zero.)",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            with transaction(self._repo.conn):
                self._repo.soft_delete_raw_material(raw_material_id)
        except Exception as e:
            QMessageBox.warning(self, "Remove failed", str(e))
            return
        self.refresh_all()
        self.data_changed.emit()
