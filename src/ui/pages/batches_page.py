from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QDateEdit,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...db.conn import transaction
from ...repo import Repo
from ..page_header import make_page_header
from ..theme import apply_primary_button, format_batch_code, normalize_batch_no
from ..qt_icons import trash_icon_button_size, trash_row_icon

# Full-row selection fill (avoids “outline only” on some Windows styles) + zebra striping
_TABLE_STYLE = (
    "QTableWidget { alternate-background-color: #f5f5f5; gridline-color: #e0e0e0; }"
    "QTableWidget::item:selected { background-color: #cce8ff; color: #000; }"
    "QTableWidget::item:selected:!active { background-color: #cce8ff; color: #000; }"
)


class BatchesConsumptionTab(QWidget):
    """Create batches and record RM consumption (FIFO or manual lot)."""

    data_changed = Signal()

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo
        self._select_batch_id_after_reload: int | None = None

        root = QVBoxLayout(self)
        hint = QLabel(
            "Create a batch with your batch no. (code = B + date + batch no., e.g. B-060426-PB01). "
            "Record RM using FIFO or a chosen lot. For yield, conversion ₹ per kg of output, and blended ₹/kg, "
            "open the Batch costing tab."
        )
        hint.setStyleSheet("color:#444; font-size:13px;")
        hint.setWordWrap(True)
        root.addWidget(hint)

        new_box = QGroupBox("New batch")
        new_lay = QVBoxLayout(new_box)
        row1 = QHBoxLayout()
        self.new_batch_no = QLineEdit()
        self.new_batch_no.setMinimumHeight(32)
        self.new_batch_no.setPlaceholderText("Batch no. (e.g. PB01)")
        self.new_batch_no.setToolTip(
            "Your manufacturing batch number (letters/digits only). Full code = B-DDMMYY-batchno."
        )
        row1.addWidget(QLabel("Batch no."))
        row1.addWidget(self.new_batch_no, 1)
        self.new_product_cb = QComboBox()
        self.new_product_cb.setMinimumHeight(32)
        self.new_product_cb.setMinimumWidth(200)
        row1.addWidget(QLabel("Product"))
        row1.addWidget(self.new_product_cb, 2)
        self.new_batch_date = QDateEdit()
        self.new_batch_date.setCalendarPopup(True)
        self.new_batch_date.setDisplayFormat("dd-MM-yyyy")
        t = date.today()
        self.new_batch_date.setDate(QDate(t.year, t.month, t.day))
        self.new_batch_date.setMinimumHeight(32)
        row1.addWidget(QLabel("Date"))
        row1.addWidget(self.new_batch_date)
        self.new_notes = QLineEdit()
        self.new_notes.setMinimumHeight(32)
        self.new_notes.setPlaceholderText("Optional notes")
        row1.addWidget(QLabel("Notes"))
        row1.addWidget(self.new_notes, 2)
        self.btn_create_batch = QPushButton("Create batch")
        self.btn_create_batch.setMinimumHeight(34)
        row1.addWidget(self.btn_create_batch)
        new_lay.addLayout(row1)
        self.lbl_next_batch = QLabel("Batch code: —")
        self.lbl_next_batch.setStyleSheet("font-weight:600;")
        new_lay.addWidget(self.lbl_next_batch)
        root.addWidget(new_box)

        split = QGridLayout()
        split.setColumnStretch(0, 1)
        split.setColumnStretch(1, 1)

        left = QVBoxLayout()
        left.addWidget(QLabel("Batches"))
        self.tbl_batches = QTableWidget(0, 5)
        self.tbl_batches.setHorizontalHeaderLabels(
            ["Batch code", "Product", "Date", "Notes", ""]
        )
        bh = self.tbl_batches.horizontalHeader()
        bh.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        bh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        bh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        bh.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        bh.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        bh.resizeSection(4, 44)
        self.tbl_batches.setAlternatingRowColors(True)
        self.tbl_batches.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_batches.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_batches.setStyleSheet(_TABLE_STYLE)
        left.addWidget(self.tbl_batches, 1)
        split.addLayout(left, 0, 0)

        right = QVBoxLayout()
        self.grp_consume = QGroupBox("RM consumption (select a batch)")
        cons_outer = QVBoxLayout(self.grp_consume)
        self.lbl_batch_head = QLabel("—")
        self.lbl_batch_head.setStyleSheet("font-weight:600;")
        cons_outer.addWidget(self.lbl_batch_head)
        self.tbl_cons = QTableWidget(0, 5)
        self.tbl_cons.setHorizontalHeaderLabels(
            ["RM", "Lot code", "Qty", "Mode", ""]
        )
        ch = self.tbl_cons.horizontalHeader()
        for c in range(4):
            ch.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        ch.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        ch.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)
        ch.resizeSection(4, 44)
        self.tbl_cons.setAlternatingRowColors(True)
        self.tbl_cons.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl_cons.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl_cons.setStyleSheet(_TABLE_STYLE)
        cons_outer.addWidget(self.tbl_cons, 1)

        add_form = QFormLayout()
        self.add_rm_cb = QComboBox()
        self.add_rm_cb.setMinimumHeight(32)
        add_form.addRow("RM code", self.add_rm_cb)
        self.add_qty = QDoubleSpinBox()
        self.add_qty.setDecimals(3)
        self.add_qty.setMaximum(1e12)
        self.add_qty.setMinimum(0.001)
        self.add_qty.setValue(1.0)
        self.add_qty.setMinimumHeight(32)
        add_form.addRow("Quantity", self.add_qty)
        mode_row = QHBoxLayout()
        self.rb_fifo = QRadioButton("FIFO (oldest lots first)")
        self.rb_manual = QRadioButton("Manual lot")
        self.rb_fifo.setChecked(True)
        self._mode_grp = QButtonGroup(self)
        self._mode_grp.addButton(self.rb_fifo)
        self._mode_grp.addButton(self.rb_manual)
        mode_row.addWidget(self.rb_fifo)
        mode_row.addWidget(self.rb_manual)
        mode_row.addStretch(1)
        add_form.addRow("Allocation", mode_row)
        self.add_lot_cb = QComboBox()
        self.add_lot_cb.setMinimumHeight(32)
        add_form.addRow("Lot (manual)", self.add_lot_cb)
        self.btn_add_cons = QPushButton("Add consumption")
        self.btn_add_cons.setMinimumHeight(36)
        add_form.addRow(self.btn_add_cons)
        cons_outer.addLayout(add_form)
        right.addWidget(self.grp_consume, 1)
        split.addLayout(right, 0, 1)
        root.addLayout(split, 1)

        bar = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setMinimumHeight(34)
        bar.addWidget(self.btn_refresh)
        bar.addStretch(1)
        root.addLayout(bar)

        self.btn_create_batch.clicked.connect(self._create_batch)
        self.new_batch_no.textChanged.connect(lambda *_: self._update_next_batch_preview())
        self.new_batch_date.dateChanged.connect(lambda *_: self._update_next_batch_preview())
        self.new_product_cb.currentIndexChanged.connect(lambda *_: self._update_next_batch_preview())
        self.btn_refresh.clicked.connect(self.refresh_all)
        self.tbl_batches.itemSelectionChanged.connect(self._on_batch_selection_changed)
        self.add_rm_cb.currentIndexChanged.connect(self._reload_lot_combo)
        self.rb_fifo.toggled.connect(self._update_lot_combo_enabled)
        self.rb_manual.toggled.connect(self._update_lot_combo_enabled)
        self.btn_add_cons.clicked.connect(self._add_consumption)

        self._update_consume_panel_enabled()
        self.refresh_all()

    def _update_next_batch_preview(self) -> None:
        has_product = self.new_product_cb.currentData() is not None
        raw_bn = self.new_batch_no.text().strip()
        if not raw_bn:
            self.lbl_next_batch.setText("Batch code: —")
            self.btn_create_batch.setEnabled(False)
            return
        qd = self.new_batch_date.date()
        bd = date(qd.year(), qd.month(), qd.day())
        try:
            normalize_batch_no(raw_bn)
            code = format_batch_code(raw_bn, bd)
            self.lbl_next_batch.setText(f"Batch code: {code}")
            self.btn_create_batch.setEnabled(has_product)
        except Exception as e:
            self.lbl_next_batch.setText(f"Batch code: — ({e})")
            self.btn_create_batch.setEnabled(False)

    def refresh_all(self) -> None:
        self._reload_product_combo()
        self._update_next_batch_preview()
        self._reload_rm_combo()
        sel = self._current_batch_id()
        self._reload_batches_table(
            select_id=self._select_batch_id_after_reload if self._select_batch_id_after_reload else sel
        )
        self._select_batch_id_after_reload = None
        self._reload_consumption_table()
        self._update_consume_panel_enabled()

    def _reload_product_combo(self) -> None:
        rows = self._repo.list_items()
        self.new_product_cb.blockSignals(True)
        self.new_product_cb.clear()
        for r in rows:
            self.new_product_cb.addItem(str(r["name"]), int(r["id"]))
        self.new_product_cb.blockSignals(False)
        self._update_next_batch_preview()

    def _reload_rm_combo(self) -> None:
        rows = self._repo.list_raw_materials()
        self.add_rm_cb.blockSignals(True)
        self.add_rm_cb.clear()
        for r in rows:
            self.add_rm_cb.addItem(str(r["short_code"]), int(r["id"]))
        self.add_rm_cb.blockSignals(False)
        self._reload_lot_combo()

    def _reload_lot_combo(self) -> None:
        self.add_lot_cb.blockSignals(True)
        self.add_lot_cb.clear()
        rid = self.add_rm_cb.currentData()
        if rid is not None:
            for row in self._repo.list_rm_lots_with_remaining(int(rid)):
                self.add_lot_cb.addItem(
                    f"{row['lot_code']}  ({float(row['qty_remaining']):,.3f} rem)",
                    int(row["id"]),
                )
        self.add_lot_cb.blockSignals(False)
        self._update_lot_combo_enabled()

    def _update_lot_combo_enabled(self) -> None:
        manual = self.rb_manual.isChecked()
        self.add_lot_cb.setEnabled(manual and self.add_lot_cb.count() > 0)

    def _reload_batches_table(self, select_id: int | None = None) -> None:
        rows = self._repo.list_production_batches()
        trash_ico = trash_row_icon()
        isz = trash_icon_button_size()
        self.tbl_batches.setRowCount(len(rows))
        pick_row = 0
        for i, r in enumerate(rows):
            bid = int(r["id"])
            if select_id is not None and bid == select_id:
                pick_row = i
            c0 = QTableWidgetItem(str(r["batch_code"]))
            c0.setData(Qt.ItemDataRole.UserRole, bid)
            self.tbl_batches.setItem(i, 0, c0)
            self.tbl_batches.setItem(i, 1, QTableWidgetItem(str(r["product_name"])))
            self.tbl_batches.setItem(i, 2, QTableWidgetItem(str(r["batch_date"])))
            n = str(r["notes"] or "").strip()
            nit = QTableWidgetItem(n[:60] + ("…" if len(n) > 60 else ""))
            if len(n) > 60:
                nit.setToolTip(n)
            self.tbl_batches.setItem(i, 3, nit)
            btn = QPushButton()
            btn.setIcon(trash_ico)
            btn.setIconSize(isz)
            btn.setToolTip("Delete batch (restores RM to lots)")
            btn.setFlat(True)
            btn.setFixedSize(36, 28)
            btn.clicked.connect(lambda checked=False, x=bid: self._delete_batch(x))
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(2, 2, 2, 2)
            hl.addWidget(btn)
            self.tbl_batches.setCellWidget(i, 4, w)
        if rows:
            self.tbl_batches.selectRow(pick_row)
        else:
            self.tbl_batches.clearSelection()

    def _current_batch_id(self) -> int | None:
        r = self.tbl_batches.currentRow()
        if r < 0:
            return None
        it = self.tbl_batches.item(r, 0)
        if it is None:
            return None
        v = it.data(Qt.ItemDataRole.UserRole)
        return int(v) if v is not None else None

    def _on_batch_selection_changed(self) -> None:
        self._reload_consumption_table()
        self._update_consume_panel_enabled()

    def _reload_consumption_table(self) -> None:
        bid = self._current_batch_id()
        self.tbl_cons.setRowCount(0)
        if bid is None:
            self.lbl_batch_head.setText("—")
            return
        b = self._repo.get_production_batch(bid)
        if b is None:
            self.lbl_batch_head.setText("—")
            return
        self.lbl_batch_head.setText(
            f"{b['batch_code']}  ·  {b['product_name']}  ·  {b['batch_date']}"
        )
        trash_ico = trash_row_icon()
        isz = trash_icon_button_size()
        lines = self._repo.list_batch_rm_consumption(bid)
        self.tbl_cons.setRowCount(len(lines))
        for i, ln in enumerate(lines):
            lid = int(ln["id"])
            self.tbl_cons.setItem(i, 0, QTableWidgetItem(str(ln["rm_code"])))
            self.tbl_cons.setItem(i, 1, QTableWidgetItem(str(ln["lot_code"])))
            q = QTableWidgetItem(f"{float(ln['qty_consumed']):,.3f}")
            q.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tbl_cons.setItem(i, 2, q)
            src = str(ln["source"])
            self.tbl_cons.setItem(
                i,
                3,
                QTableWidgetItem("FIFO" if src == "fifo" else "Manual"),
            )
            btn = QPushButton()
            btn.setIcon(trash_ico)
            btn.setIconSize(isz)
            btn.setToolTip("Remove line (restore qty to lot)")
            btn.setFlat(True)
            btn.setFixedSize(36, 28)
            btn.clicked.connect(lambda checked=False, x=lid: self._remove_line(x))
            w = QWidget()
            hl = QHBoxLayout(w)
            hl.setContentsMargins(2, 2, 2, 2)
            hl.addWidget(btn)
            self.tbl_cons.setCellWidget(i, 4, w)

    def _update_consume_panel_enabled(self) -> None:
        ok = self._current_batch_id() is not None
        self.grp_consume.setEnabled(ok)
        self.btn_add_cons.setEnabled(ok and self.add_rm_cb.count() > 0)

    def _create_batch(self) -> None:
        iid = self.new_product_cb.currentData()
        if iid is None:
            QMessageBox.information(
                self,
                "Products",
                "Add products under Setup (Seed Data) before creating a batch.",
            )
            return
        bn = self.new_batch_no.text().strip()
        if not bn:
            QMessageBox.warning(self, "Batch no.", "Enter a batch number.")
            return
        qd = self.new_batch_date.date()
        bd = date(qd.year(), qd.month(), qd.day())
        try:
            with transaction(self._repo.conn):
                bid, code = self._repo.create_production_batch(
                    bn, int(iid), bd, notes=self.new_notes.text()
                )
        except Exception as e:
            QMessageBox.warning(self, "Create failed", str(e))
            return
        self._select_batch_id_after_reload = bid
        self.new_notes.clear()
        self.refresh_all()
        self.data_changed.emit()
        QMessageBox.information(self, "Batch", f"Created {code}")

    def _delete_batch(self, batch_id: int) -> None:
        b = self._repo.get_production_batch(batch_id)
        label = str(b["batch_code"]) if b else str(batch_id)
        if (
            QMessageBox.question(
                self,
                "Delete batch",
                f"Delete batch “{label}” and restore all consumed quantities to their lots?",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self._repo.delete_production_batch(batch_id)
        except Exception as e:
            QMessageBox.warning(self, "Delete failed", str(e))
            return
        self.refresh_all()
        self.data_changed.emit()

    def _add_consumption(self) -> None:
        bid = self._current_batch_id()
        if bid is None:
            return
        rid = self.add_rm_cb.currentData()
        if rid is None:
            QMessageBox.information(self, "RM", "No raw materials in master.")
            return
        qty = float(self.add_qty.value())
        if qty <= 0:
            QMessageBox.warning(self, "Invalid", "Quantity must be > 0.")
            return
        try:
            if self.rb_fifo.isChecked():
                self._repo.add_batch_consumption_fifo(bid, int(rid), qty)
            else:
                lid = self.add_lot_cb.currentData()
                if lid is None:
                    raise ValueError("Choose a lot for manual allocation.")
                self._repo.add_batch_consumption_manual(
                    bid, int(lid), qty, raw_material_id=int(rid)
                )
        except Exception as e:
            QMessageBox.warning(self, "Add failed", str(e))
            return
        self._reload_lot_combo()
        self._reload_consumption_table()
        self.data_changed.emit()

    def _remove_line(self, line_id: int) -> None:
        try:
            self._repo.remove_batch_consumption_line(line_id)
        except Exception as e:
            QMessageBox.warning(self, "Remove failed", str(e))
            return
        self._reload_lot_combo()
        self._reload_consumption_table()
        self.data_changed.emit()


class BatchCostingTab(QWidget):
    """Yield, conversion ₹ per kg of output, and blended ₹/kg — separate from consumption UI."""

    data_changed = Signal()
    fg_help_navigate = Signal(str)

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo

        root = QVBoxLayout(self)
        intro = QLabel(
            "RM cost = sum of (consumption × lot unit cost). "
            "Conversion is a fixed ₹ rate per kg of finished output (labour, power, packing, etc.). "
            "Blended ₹/kg = (RM cost ÷ yield) + conversion ₹/kg. Set yield when output is known, then Save."
        )
        intro.setStyleSheet("color:#444; font-size:13px;")
        intro.setWordWrap(True)
        root.addWidget(intro)

        filt = QHBoxLayout()
        filt.addWidget(QLabel("Product filter"))
        self.filter_product_cb = QComboBox()
        self.filter_product_cb.setMinimumHeight(32)
        filt.addWidget(self.filter_product_cb, 1)
        root.addLayout(filt)

        self.tbl = QTableWidget(0, 7)
        self.tbl.setHorizontalHeaderLabels(
            ["Batch code", "Product", "Date", "RM ₹", "Yield kg", "Conv. ₹/kg", "₹/kg out"]
        )
        th = self.tbl.horizontalHeader()
        th.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        th.resizeSection(1, 140)
        th.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        for c in (3, 4, 5):
            th.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        th.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.tbl.setAlternatingRowColors(True)
        self.tbl.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.setStyleSheet(_TABLE_STYLE)
        root.addWidget(self.tbl, 1)

        detail = QGroupBox("Selected batch — edit and save")
        df = QFormLayout(detail)
        self.lbl_pick = QLabel("Select a batch in the table.")
        self.lbl_pick.setStyleSheet("font-weight:600;")
        df.addRow(self.lbl_pick)
        self.lbl_rm_detail = QLabel("—")
        df.addRow("RM cost (₹)", self.lbl_rm_detail)
        self.sp_yield = QDoubleSpinBox()
        self.sp_yield.setDecimals(3)
        self.sp_yield.setMaximum(1e12)
        self.sp_yield.setMinimum(0)
        self.sp_yield.setSpecialValueText("Not set")
        self.sp_yield.setMinimumHeight(32)
        self.sp_yield.setToolTip("Total kg of finished output for this batch.")
        df.addRow("Yield (kg output)", self.sp_yield)
        self.sp_conv = QDoubleSpinBox()
        self.sp_conv.setDecimals(2)
        self.sp_conv.setMaximum(1e12)
        self.sp_conv.setMinimum(0)
        self.sp_conv.setMinimumHeight(32)
        self.sp_conv.setToolTip("Conversion and overhead expressed as ₹ per kg of finished output.")
        df.addRow("Conversion & overhead (₹ per kg of output)", self.sp_conv)
        self.lbl_cpk = QLabel("—")
        df.addRow("Blended cost per kg of output", self.lbl_cpk)
        self.btn_save = QPushButton("Save yield & conversion ₹/kg")
        self.btn_save.setMinimumHeight(38)
        apply_primary_button(self.btn_save)
        self.btn_save.setEnabled(False)
        df.addRow(self.btn_save)
        root.addWidget(detail)

        br = QHBoxLayout()
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setMinimumHeight(34)
        br.addWidget(self.btn_refresh)
        br.addStretch(1)
        root.addLayout(br)

        self._selected_batch_id: int | None = None

        self.filter_product_cb.currentIndexChanged.connect(self._reload_table)
        self.tbl.itemSelectionChanged.connect(self._on_table_selection)
        self.sp_yield.valueChanged.connect(self._refresh_detail_math)
        self.sp_conv.valueChanged.connect(self._refresh_detail_math)
        self.btn_save.clicked.connect(self._save)
        self.btn_refresh.clicked.connect(self.refresh_all)

        self.refresh_all()

    def refresh_all(self) -> None:
        sel_pid = self.filter_product_cb.currentData()
        self.filter_product_cb.blockSignals(True)
        self.filter_product_cb.clear()
        self.filter_product_cb.addItem("All products", None)
        for it in self._repo.list_items():
            self.filter_product_cb.addItem(str(it["name"]), int(it["id"]))
        if sel_pid is not None:
            idx = self.filter_product_cb.findData(sel_pid)
            if idx >= 0:
                self.filter_product_cb.setCurrentIndex(idx)
        self.filter_product_cb.blockSignals(False)
        self._reload_table()

    def _reload_table(self) -> None:
        pid = self.filter_product_cb.currentData()
        rows = self._repo.list_production_batches()
        if pid is not None:
            rows = [r for r in rows if int(r["product_item_id"]) == int(pid)]

        self.tbl.setRowCount(len(rows))
        preserve = self._selected_batch_id
        pick_row = -1
        for i, r in enumerate(rows):
            bid = int(r["id"])
            if preserve is not None and bid == preserve:
                pick_row = i
            rm = self._repo.batch_rm_material_cost(bid)
            y = r["batch_yield_kg"]
            y_s = f"{float(y):,.3f}" if y is not None and float(y) > 1e-12 else "—"
            conv_pu = float(r["conversion_cost_per_kg"] or 0)
            cpk = self._repo.production_batch_cost_per_kg(bid)
            cpk_s = f"{cpk:,.2f}" if cpk is not None else "—"

            c0 = QTableWidgetItem(str(r["batch_code"]))
            c0.setData(Qt.ItemDataRole.UserRole, bid)
            self.tbl.setItem(i, 0, c0)
            pname = str(r["product_name"])
            p_disp = pname[:18] + "…" if len(pname) > 18 else pname
            pit = QTableWidgetItem(p_disp)
            if len(pname) > 18:
                pit.setToolTip(pname)
            self.tbl.setItem(i, 1, pit)
            self.tbl.setItem(i, 2, QTableWidgetItem(str(r["batch_date"])))
            for col, txt in ((3, f"{rm:,.2f}"), (4, y_s), (5, f"{conv_pu:,.2f}"), (6, cpk_s)):
                it = QTableWidgetItem(txt)
                it.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.tbl.setItem(i, col, it)

        if pick_row >= 0:
            self.tbl.selectRow(pick_row)
        elif rows:
            self.tbl.selectRow(0)
        else:
            self.tbl.clearSelection()
            self._clear_detail()

    def _on_table_selection(self) -> None:
        r = self.tbl.currentRow()
        if r < 0:
            self._clear_detail()
            return
        it = self.tbl.item(r, 0)
        if it is None:
            self._clear_detail()
            return
        bid = it.data(Qt.ItemDataRole.UserRole)
        if bid is None:
            self._clear_detail()
            return
        self._selected_batch_id = int(bid)
        b = self._repo.get_production_batch(self._selected_batch_id)
        if b is None:
            self._clear_detail()
            return
        self.lbl_pick.setText(f"{b['batch_code']}  ·  {b['product_name']}")
        rm = self._repo.batch_rm_material_cost(self._selected_batch_id)
        self.lbl_rm_detail.setText(f"{rm:,.2f}")
        self.sp_yield.blockSignals(True)
        self.sp_conv.blockSignals(True)
        y = b["batch_yield_kg"]
        if y is None or float(y) <= 1e-12:
            self.sp_yield.setValue(0)
        else:
            self.sp_yield.setValue(float(y))
        self.sp_conv.setValue(float(b["conversion_cost_per_kg"] or 0))
        self.sp_yield.blockSignals(False)
        self.sp_conv.blockSignals(False)
        self.btn_save.setEnabled(True)
        self._refresh_detail_math()

    def _clear_detail(self) -> None:
        self._selected_batch_id = None
        self.lbl_pick.setText("Select a batch in the table.")
        self.lbl_rm_detail.setText("—")
        self.sp_yield.blockSignals(True)
        self.sp_conv.blockSignals(True)
        self.sp_yield.setValue(0)
        self.sp_conv.setValue(0)
        self.sp_yield.blockSignals(False)
        self.sp_conv.blockSignals(False)
        self.lbl_cpk.setText("—")
        self.btn_save.setEnabled(False)

    def _refresh_detail_math(self) -> None:
        if self._selected_batch_id is None:
            self.lbl_cpk.setText("—")
            return
        rm = self._repo.batch_rm_material_cost(self._selected_batch_id)
        conv_pu = float(self.sp_conv.value())
        yv = float(self.sp_yield.value())
        if yv <= 1e-12:
            self.lbl_cpk.setText("— (set yield to compute)")
        else:
            self.lbl_cpk.setText(f"{rm / yv + conv_pu:,.2f}")

    def _save(self) -> None:
        bid = self._selected_batch_id
        if bid is None:
            return
        yv = float(self.sp_yield.value())
        yield_kg = None if yv <= 1e-12 else yv
        try:
            self._repo.update_production_batch_costing(
                bid,
                batch_yield_kg=yield_kg,
                conversion_cost_per_kg=float(self.sp_conv.value()),
            )
        except Exception as e:
            msg = str(e)
            partial = "Yield and conversion were saved" in msg
            if partial:
                box = QMessageBox(self)
                box.setIcon(QMessageBox.Icon.Warning)
                box.setWindowTitle("Yield saved — stock warning")
                box.setText(msg)
                btn_seed = box.addButton("Open Seed Data", QMessageBox.ButtonRole.ActionRole)
                btn_cost = box.addButton("Open Batch costing", QMessageBox.ButtonRole.ActionRole)
                box.addButton(QMessageBox.StandardButton.Ok)
                box.exec()
                clicked = box.clickedButton()
                if clicked == btn_seed:
                    self.fg_help_navigate.emit("seed_data")
                elif clicked == btn_cost:
                    self.fg_help_navigate.emit("batch_costing")
                self._reload_table()
                self._on_table_selection()
                self.data_changed.emit()
            else:
                QMessageBox.warning(self, "Save failed", msg)
            return
        b = self._repo.get_production_batch(bid)
        ok_msg = "Yield saved to database."
        if b is not None:
            y = b["batch_yield_kg"]
            if y is not None and float(y) > 1e-12:
                if self._repo.raw_material_id_for_finished_product(int(b["product_item_id"])) is None:
                    ok_msg += (
                        "\n\nNo raw material row is linked to this product for finished stock. "
                        "In Setup → Seed Data, edit your FG row (e.g. code LP750) and set "
                        "“Finished-good stock for product”."
                    )
        QMessageBox.information(self, "Batch costing", ok_msg)
        self._reload_table()
        self._on_table_selection()
        self.data_changed.emit()


class ProductionPage(QWidget):
    """Production: tab 1 = batches & RM consumption; tab 2 = costing."""

    data_changed = Signal()
    fg_help_navigate = Signal(str)

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(
            make_page_header(
                "Production",
                "Create batches, record RM consumption (FIFO), and set yield and cost per kg.",
            )
        )

        self._tabs = QTabWidget()
        self._tab_batches = BatchesConsumptionTab(repo)
        self._tab_costing = BatchCostingTab(repo)
        self._tab_costing.fg_help_navigate.connect(self.fg_help_navigate.emit)
        self._tabs.addTab(self._tab_batches, "Batches && consumption")
        self._tabs.addTab(self._tab_costing, "Batch costing")
        lay.addWidget(self._tabs, 1)

        self._tab_batches.data_changed.connect(self._on_any_change)
        self._tab_costing.data_changed.connect(self._on_any_change)

    def open_batch_costing_tab(self) -> None:
        self._tabs.setCurrentIndex(1)

    def _on_any_change(self) -> None:
        self._tab_batches.refresh_all()
        self._tab_costing.refresh_all()
        self.data_changed.emit()

    def refresh_all(self) -> None:
        self._tab_batches.refresh_all()
        self._tab_costing.refresh_all()


# Backward-compatible name for imports
BatchesPage = ProductionPage
