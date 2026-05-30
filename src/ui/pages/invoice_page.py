from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...db.conn import transaction
from ...open_file import open_local_file
from ...excel_generate import (
    GenerateInvoiceInput,
    InvoiceLine,
    _number_to_words,
    compute_gst_invoice_totals,
    format_invoice_customer_display_name,
    generate_invoice_excel,
)
from ...repo import Repo
from ..page_header import make_page_header
from ..theme import apply_primary_button


def _safe_filename(s: str) -> str:
    s = re.sub(r"[\\\\/:*?\"<>|]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


class _NoWheelComboBox(QComboBox):
    def wheelEvent(self, event) -> None:  # type: ignore[override]
        # Prevent accidental changes when scrolling the page.
        event.ignore()


class InvoicePage(QWidget):
    created = Signal()

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo

        outer = QVBoxLayout(self)
        outer.addWidget(
            make_page_header(
                "Invoices",
                "Generate GST-style Excel from your template; line totals and grand total are computed in the app.",
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll, 1)

        container = QWidget()
        scroll.setWidget(container)
        layout = QVBoxLayout(container)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)

        def add_pair(row: int, l1: str, w1: QWidget, l2: str, w2: QWidget) -> None:
            grid.addWidget(QLabel(l1), row, 0)
            grid.addWidget(w1, row, 1)
            grid.addWidget(QLabel(l2), row, 2)
            grid.addWidget(w2, row, 3)

        self.customer_cb = _NoWheelComboBox()
        self.customer_cb.setMinimumHeight(30)
        self.customer_cb.addItem("Select customer…", None)
        self.inv_no = QLineEdit()
        self.inv_no.setMinimumHeight(30)
        self.inv_no.setPlaceholderText("001")
        self.inv_date = QLineEdit()
        self.inv_date.setMinimumHeight(30)
        self.inv_date.setText(date.today().strftime("%d.%m.%Y"))

        add_pair(0, "Customer", self.customer_cb, "Invoice date", self.inv_date)
        inv_no_row = QWidget()
        inv_no_lay = QHBoxLayout(inv_no_row)
        inv_no_lay.setContentsMargins(0, 0, 0, 0)
        inv_no_lay.setSpacing(8)
        inv_no_lay.addWidget(self.inv_no, 1)
        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.setMinimumHeight(30)
        self.btn_refresh.setToolTip("Reload customers and products; set next invoice number for this date.")
        inv_no_lay.addWidget(self.btn_refresh)
        grid.addWidget(QLabel("Invoice no"), 1, 0)
        grid.addWidget(inv_no_row, 1, 1, 1, 3)

        self.transport = QLineEdit()
        self.transport.setMinimumHeight(30)
        self.eway = QLineEdit()
        self.eway.setMinimumHeight(30)
        add_pair(2, "Transport mode", self.transport, "E-way bill no", self.eway)

        self.payment_terms = QLineEdit()
        self.payment_terms.setMinimumHeight(30)
        self.place_supply = QLineEdit()
        self.place_supply.setMinimumHeight(30)
        add_pair(3, "Payment terms", self.payment_terms, "Place of supply", self.place_supply)

        self.po_no = QLineEdit()
        self.po_no.setMinimumHeight(30)
        self.po_date = QLineEdit()
        self.po_date.setMinimumHeight(30)
        self.po_date.setPlaceholderText("dd.mm.yyyy (optional)")
        add_pair(4, "P.O. no", self.po_no, "P.O. date", self.po_date)

        # Customer fields (editable for this invoice). Master updates happen in Setup.
        self.cust_name = QLineEdit()
        self.cust_name.setMinimumHeight(30)
        self.cust_address = QTextEdit()
        self.cust_address.setFixedHeight(60)
        add_pair(5, "Customer name", self.cust_name, "Address", self.cust_address)

        self.cust_gstin = QLineEdit()
        self.cust_gstin.setMinimumHeight(30)
        self.cust_state = QLineEdit()
        self.cust_state.setMinimumHeight(30)
        add_pair(6, "GSTIN", self.cust_gstin, "State", self.cust_state)

        self.cust_state_code = QLineEdit()
        self.cust_state_code.setMinimumHeight(30)
        grid.addWidget(QLabel("State code"), 7, 0)
        grid.addWidget(self.cust_state_code, 7, 1)

        self.ship_same = QCheckBox("Shipped To same as Billed To")
        self.ship_same.setChecked(False)
        grid.addWidget(self.ship_same, 8, 0, 1, 4)

        self.ship_name = QLineEdit()
        self.ship_name.setMinimumHeight(30)
        self.ship_address = QTextEdit()
        self.ship_address.setFixedHeight(60)
        add_pair(9, "Ship name", self.ship_name, "Ship address", self.ship_address)

        self.ship_gstin = QLineEdit()
        self.ship_gstin.setMinimumHeight(30)
        self.ship_state = QLineEdit()
        self.ship_state.setMinimumHeight(30)
        add_pair(10, "Ship GSTIN", self.ship_gstin, "Ship state", self.ship_state)

        self.ship_state_code = QLineEdit()
        self.ship_state_code.setMinimumHeight(30)
        grid.addWidget(QLabel("Ship state code"), 11, 0)
        grid.addWidget(self.ship_state_code, 11, 1)

        layout.addLayout(grid)

        items_label = QLabel("Product lines (max 7)")
        items_label.setStyleSheet("font-size:15px; font-weight:600;")
        layout.addWidget(items_label)

        self._item_validator = QDoubleValidator(0.0, 1e9, 3)
        self._item_validator.setNotation(QDoubleValidator.Notation.StandardNotation)

        self.items_box = QWidget()
        self.items_layout = QVBoxLayout(self.items_box)
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(8)
        layout.addWidget(self.items_box)

        self.item_rows: list[dict] = []

        row_btns = QHBoxLayout()
        self.btn_add_row = QPushButton("+ Add line")
        self.btn_add_row.setMinimumHeight(34)
        row_btns.addWidget(self.btn_add_row)
        row_btns.addStretch(1)
        layout.addLayout(row_btns)

        self.btn_generate = QPushButton("Preview & generate invoice (.xlsx)")
        self.btn_generate.setMinimumHeight(40)
        apply_primary_button(self.btn_generate)
        layout.addWidget(self.btn_generate)

        hint = QLabel(
            "Uses Settings → template path + output folder. "
            "Totals: 18% GST on line subtotal; grand total written to cell O43 (same as bulk import)."
        )
        hint.setStyleSheet("color:#444;")
        layout.addWidget(hint)

        layout.addStretch(1)

        self.btn_generate.clicked.connect(self._generate)
        self.btn_refresh.clicked.connect(self._refresh_invoice_page)
        self.btn_add_row.clicked.connect(self._add_item_card)
        self.customer_cb.currentIndexChanged.connect(self._on_customer_changed)
        self.ship_same.toggled.connect(self._toggle_ship_fields)
        self.reload_customers()
        self._rebuild_item_options()
        self._toggle_ship_fields()
        self._wire_validation()
        self._add_item_card()
        self._update_generate_enabled()

    def reload_customers(self, restore_customer_id: int | None = None) -> None:
        self.customer_cb.clear()
        self.customer_cb.addItem("Select customer…", None)
        for c in self._repo.list_customers():
            self.customer_cb.addItem(str(c["name"]), int(c["id"]))
        if restore_customer_id is not None:
            idx = self.customer_cb.findData(restore_customer_id)
            if idx >= 0:
                self.customer_cb.setCurrentIndex(idx)
                self._load_customer_into_fields()
                return
        self.customer_cb.setCurrentIndex(0)
        self._clear_customer_fields()

    def _suggest_next_invoice_no(self) -> None:
        try:
            inv_date_iso = datetime.strptime(self.inv_date.text().strip(), "%d.%m.%Y").date()
        except Exception:
            inv_date_iso = date.today()
        n = self._repo.get_next_invoice_serial(inv_date_iso)
        self.inv_no.setText(f"{n:03d}")

    def _refresh_invoice_page(self) -> None:
        cid = self.customer_cb.currentData()
        rid = int(cid) if cid is not None else None
        self.reload_customers(restore_customer_id=rid)
        self._rebuild_item_options()
        self._suggest_next_invoice_no()
        self._update_generate_enabled()

    def reload_items(self) -> None:
        self._rebuild_item_options()

    def _add_item_card(self) -> None:
        if len(self.item_rows) >= 7:
            return

        card = QWidget()
        card_v = QVBoxLayout(card)
        card_v.setContentsMargins(0, 0, 0, 0)
        card_v.setSpacing(6)
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)

        item_cb = _NoWheelComboBox()
        item_cb.setEditable(True)
        item_cb.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        item_cb.setMinimumHeight(32)
        item_cb.setMinimumWidth(280)

        hsn = QLineEdit()
        hsn.setMinimumHeight(32)
        hsn.setFixedWidth(100)
        hsn.setPlaceholderText("HSN")

        qty = QLineEdit()
        qty.setMinimumHeight(32)
        qty.setFixedWidth(80)
        qty.setPlaceholderText("Qty")
        qty.setValidator(self._item_validator)

        unit = QLineEdit()
        unit.setMinimumHeight(32)
        unit.setFixedWidth(70)
        unit.setPlaceholderText("Unit")
        unit.setText("Kgs")

        rate = QLineEdit()
        rate.setMinimumHeight(32)
        rate.setFixedWidth(90)
        rate.setPlaceholderText("Rate")
        rate.setValidator(self._item_validator)

        btn_remove = QPushButton("Remove")
        btn_remove.setObjectName("btnTableAction")
        btn_remove.setMinimumHeight(32)
        btn_remove.setCursor(Qt.CursorShape.PointingHandCursor)

        row_layout.addWidget(item_cb, 3)
        row_layout.addWidget(QLabel("HSN"), 0)
        row_layout.addWidget(hsn, 0)
        row_layout.addWidget(qty, 0)
        row_layout.addWidget(unit, 0)
        row_layout.addWidget(rate, 0)
        row_layout.addWidget(btn_remove, 0)
        card_v.addLayout(row_layout)

        line_note = QLineEdit()
        line_note.setMinimumHeight(30)
        line_note.setPlaceholderText(
            "Optional note on invoice (after product name, e.g. shade / remarks). Stock uses the product only."
        )
        card_v.addWidget(line_note)

        batch_row = QHBoxLayout()
        batch_row.setContentsMargins(0, 0, 0, 0)
        batch_row.setSpacing(8)
        batch_cb = _NoWheelComboBox()
        batch_cb.setMinimumHeight(32)
        batch_cb.setMinimumWidth(380)
        batch_cb.setToolTip(
            "Optional: production batch code for this line (filtered by product). Used for costing."
        )
        batch_row.addWidget(QLabel("Batch code"))
        batch_row.addWidget(batch_cb, 1)
        card_v.addLayout(batch_row)

        fg_stock_hint = QLabel("")
        fg_stock_hint.setStyleSheet("color:#555; font-size:12px;")
        fg_stock_hint.setWordWrap(True)
        fg_stock_hint.setVisible(False)
        card_v.addWidget(fg_stock_hint)

        self.items_layout.addWidget(card)

        entry = {
            "row": card,
            "item_cb": item_cb,
            "line_note": line_note,
            "batch_cb": batch_cb,
            "fg_stock_hint": fg_stock_hint,
            "hsn": hsn,
            "qty": qty,
            "unit": unit,
            "rate": rate,
            "btn_remove": btn_remove,
        }
        self.item_rows.append(entry)

        btn_remove.clicked.connect(lambda _=False, e=entry: self._remove_item_card(e))
        item_cb.currentIndexChanged.connect(lambda _=0, e=entry: self._on_item_card_selected(e))
        item_cb.editTextChanged.connect(lambda _=None, e=entry: self._on_item_line_text_changed(e))
        line_note.textChanged.connect(lambda *_a, e=entry: self._on_line_note_or_batch_changed(e))
        hsn.textChanged.connect(lambda _=None: self._update_generate_enabled())
        qty.textChanged.connect(lambda *_a, e=entry: self._on_qty_changed_for_hint(e))
        rate.textChanged.connect(lambda _=None: self._update_generate_enabled())
        unit.textChanged.connect(lambda _=None: self._update_generate_enabled())
        batch_cb.currentIndexChanged.connect(lambda *_a, e=entry: self._on_line_note_or_batch_changed(e))

        self._rebuild_item_options()
        self._update_generate_enabled()

    def _remove_item_card(self, entry: dict) -> None:
        if len(self.item_rows) <= 1:
            return
        w = entry["row"]
        self.items_layout.removeWidget(w)
        w.setParent(None)
        self.item_rows = [e for e in self.item_rows if e is not entry]
        self._update_generate_enabled()

    def _on_item_card_selected(self, entry: dict) -> None:
        cb: QComboBox = entry["item_cb"]
        data = cb.currentData()
        if not data:
            self._reload_batch_options_for_entry(entry)
            self._update_generate_enabled()
            return
        _item_id, hsn, unit, rate = data
        if hsn and not entry["hsn"].text().strip():
            entry["hsn"].setText(str(hsn))
        if unit:
            entry["unit"].setText(str(unit))
        if rate is not None and not entry["rate"].text().strip():
            entry["rate"].setText(str(rate))
        self._reload_batch_options_for_entry(entry)
        self._update_generate_enabled()

    def _on_item_line_text_changed(self, entry: dict) -> None:
        self._reload_batch_options_for_entry(entry)
        self._update_generate_enabled()

    def _on_line_note_or_batch_changed(self, entry: dict) -> None:
        self._update_fg_stock_hint_for_entry(entry)
        self._update_generate_enabled()

    def _on_qty_changed_for_hint(self, entry: dict) -> None:
        self._update_fg_stock_hint_for_entry(entry)
        self._update_generate_enabled()

    def _canonical_product_name_for_line(self, entry: dict) -> str:
        """Master product name when the line is tied to a catalog item; else combo text."""
        data = entry["item_cb"].currentData()
        if data:
            it = self._repo.get_item(int(data[0]))
            if it is not None:
                return str(it["name"] or "").strip()
        txt = entry["item_cb"].currentText().strip()
        for row in self._repo.list_items():
            if str(row["name"]).strip() == txt:
                return str(row["name"]).strip()
        return txt

    def _invoice_line_description(self, entry: dict) -> str:
        """Text printed on invoice / stored in DB: product name plus optional note."""
        base = self._canonical_product_name_for_line(entry)
        note = entry["line_note"].text().strip()
        if note:
            return f"{base} — {note}" if base else note
        return base

    def _update_fg_stock_hint_for_entry(self, entry: dict) -> None:
        lbl: QLabel = entry["fg_stock_hint"]
        batch_cb: QComboBox = entry["batch_cb"]
        if batch_cb.currentData() is not None:
            lbl.setText("")
            lbl.setVisible(False)
            return
        item_id = self._resolve_item_id_from_combo(entry["item_cb"])
        if item_id is None:
            lbl.setText("")
            lbl.setVisible(False)
            return
        rm_id = self._repo.raw_material_id_for_finished_product(item_id)
        if rm_id is None:
            lbl.setText("")
            lbl.setVisible(False)
            return
        oh = self._repo.raw_material_on_hand(rm_id)
        rm = self._repo.get_raw_material(rm_id)
        code = str(rm["short_code"]) if rm else "FG"
        try:
            q_need = float(entry["qty"].text().strip())
        except Exception:
            q_need = 0.0
        extra = ""
        if q_need > 1e-12:
            if oh + 1e-12 < q_need:
                extra = f"  ·  Line qty {q_need:,.3f} kg exceeds on hand"
            else:
                extra = f"  ·  After this line (~{max(0.0, oh - q_need):,.3f} kg left if invoiced)"
        lbl.setText(f"{code}: {oh:,.3f} kg on hand (FIFO when batch is none){extra}")
        lbl.setVisible(True)

    def _resolve_item_id_from_combo(self, icb: QComboBox) -> int | None:
        data = icb.currentData()
        if data:
            return int(data[0])
        text = icb.currentText().strip()
        if not text:
            return None
        for it in self._repo.list_items():
            if str(it["name"]).strip() == text:
                return int(it["id"])
        return None

    def _invoice_fg_stock_plan_error(self) -> str | None:
        """Simulate FG moves in line order (batch lots + FIFO) before preview/Excel."""
        sim_lines: list[dict] = []
        ln = 0
        for entry in self.item_rows:
            desc = self._invoice_line_description(entry)
            if not desc.strip():
                continue
            ln += 1
            try:
                qty = float(entry["qty"].text().strip())
            except Exception:
                qty = 0.0
            braw = entry["batch_cb"].currentData()
            pbid = int(braw) if braw is not None else None
            item_id = self._resolve_item_id_from_combo(entry["item_cb"])
            sim_lines.append(
                {
                    "line_no": ln,
                    "description": desc,
                    "qty": qty,
                    "production_batch_id": pbid,
                    "product_item_id": item_id,
                }
            )
        if not sim_lines:
            return None
        return self._repo.validate_invoice_fg_stock_plan(sim_lines)

    def _clear_customer_fields(self) -> None:
        self.cust_name.clear()
        self.cust_address.clear()
        self.cust_gstin.clear()
        self.cust_state.clear()
        self.cust_state_code.clear()

    def _reload_batch_options_for_entry(
        self, entry: dict, preserve_batch_id: int | None = None
    ) -> None:
        bcb: QComboBox = entry["batch_cb"]
        icb: QComboBox = entry["item_cb"]
        bcb.blockSignals(True)
        prev = preserve_batch_id
        if prev is None:
            raw = bcb.currentData()
            prev = int(raw) if raw is not None else None
        bcb.clear()
        bcb.addItem("— none —", None)
        item_id = self._resolve_item_id_from_combo(icb)
        if item_id is not None:
            for br in self._repo.list_production_batches_for_product(item_id):
                bid = int(br["id"])
                code = str(br["batch_code"])
                cpk = self._repo.production_batch_cost_per_kg(bid)
                rem = self._repo.finished_good_qty_remaining_for_batch(bid)
                rem_s = f"{rem:,.3f} kg rem" if rem is not None else "no FG lot"
                if cpk is not None:
                    label = f"{code}  ·  {rem_s}  ·  ₹{cpk:,.2f}/kg"
                    tip = (
                        f"{code} · {br['batch_date']}\n"
                        f"On hand: {rem_s}\n"
                        f"Blended cost: ₹{cpk:,.2f}/kg"
                    )
                else:
                    label = f"{code}  ·  {rem_s}  ·  cost n/a"
                    tip = (
                        f"{code} · {br['batch_date']}\n"
                        f"On hand: {rem_s}\n"
                        "Set yield on Batch costing for ₹/kg."
                    )
                bcb.addItem(label, bid)
                bcb.setItemData(
                    bcb.count() - 1,
                    tip,
                    Qt.ItemDataRole.ToolTipRole,
                )
        if prev is not None:
            idx = bcb.findData(prev)
            if idx >= 0:
                bcb.setCurrentIndex(idx)
            else:
                bcb.setCurrentIndex(0)
        else:
            bcb.setCurrentIndex(0)
        bcb.blockSignals(False)
        self._update_fg_stock_hint_for_entry(entry)

    def _rebuild_item_options(self) -> None:
        items = self._repo.list_items()
        options: list[tuple[str, object]] = [("", None)]
        for it in items:
            options.append(
                (
                    str(it["name"]),
                    (
                        int(it["id"]),
                        str(it["hsn"] or ""),
                        str(it["unit"] or ""),
                        it["default_rate"],
                    ),
                )
            )

        for entry in self.item_rows:
            cb: QComboBox = entry["item_cb"]
            current_text = cb.currentText()
            preserve_b = entry["batch_cb"].currentData()
            preserve_bid = int(preserve_b) if preserve_b is not None else None
            cb.blockSignals(True)
            cb.clear()
            for label, data in options:
                cb.addItem(label, data)
            if current_text:
                cb.setCurrentText(current_text)
                idx = cb.findText(current_text, Qt.MatchFlag.MatchExactly)
                if idx >= 0:
                    cb.setCurrentIndex(idx)
            cb.blockSignals(False)
            self._reload_batch_options_for_entry(entry, preserve_batch_id=preserve_bid)
        for entry in self.item_rows:
            self._update_fg_stock_hint_for_entry(entry)

    def _wire_validation(self) -> None:
        for w in (self.inv_no, self.inv_date, self.cust_name):
            w.textChanged.connect(self._update_generate_enabled)
        self.customer_cb.currentIndexChanged.connect(self._update_generate_enabled)

    def _set_invalid(self, w: QWidget, invalid: bool) -> None:
        if invalid:
            w.setStyleSheet("border: 2px solid #d33;")
        else:
            w.setStyleSheet("")

    def _update_generate_enabled(self) -> None:
        ok = True

        if self.customer_cb.currentIndex() <= 0:
            ok = False

        inv_no = self.inv_no.text().strip()
        inv_no_ok = bool(inv_no) and inv_no.isdigit()
        self._set_invalid(self.inv_no, not inv_no_ok)
        ok = ok and inv_no_ok

        try:
            datetime.strptime(self.inv_date.text().strip(), "%d.%m.%Y")
            inv_dt_ok = True
        except Exception:
            inv_dt_ok = False
        self._set_invalid(self.inv_date, not inv_dt_ok)
        ok = ok and inv_dt_ok

        cust_name_ok = bool(
            self.cust_name.text().strip()
            or (self.customer_cb.currentText().strip() if self.customer_cb.currentIndex() > 0 else "")
        )
        self._set_invalid(self.cust_name, not cust_name_ok)
        ok = ok and cust_name_ok

        any_line = False
        for entry in self.item_rows:
            desc = self._invoice_line_description(entry).strip()
            qty = entry["qty"].text().strip()
            rate = entry["rate"].text().strip()
            hsn = entry["hsn"].text().strip()
            if not desc and not qty and not rate and not hsn:
                self._set_invalid(entry["qty"], False)
                self._set_invalid(entry["rate"], False)
                self._set_invalid(entry["hsn"], False)
                continue
            any_line = True
            try:
                qv = float(qty)
                rv = float(rate)
                line_ok = qv > 0 and rv > 0 and bool(desc) and bool(hsn)
            except Exception:
                line_ok = False
            self._set_invalid(entry["qty"], not line_ok)
            self._set_invalid(entry["rate"], not line_ok)
            self._set_invalid(entry["hsn"], not line_ok)
            ok = ok and line_ok

        ok = ok and any_line

        self.btn_generate.setEnabled(ok)

    def _load_customer_into_fields(self) -> None:
        if self.customer_cb.currentIndex() <= 0:
            return
        customer_id = int(self.customer_cb.currentData())
        c = self._repo.get_customer(customer_id)
        if c is None:
            return
        self.cust_name.setText(str(c["name"] or ""))
        self.cust_address.setPlainText(str(c["address"] or ""))
        self.cust_gstin.setText(str(c["gstin"] or ""))
        self.cust_state.setText(str(c["state"] or ""))
        self.cust_state_code.setText(str(c["state_code"] or ""))

    def _on_customer_changed(self) -> None:
        if self.customer_cb.currentIndex() <= 0:
            self._clear_customer_fields()
            return
        self._load_customer_into_fields()
        # Auto-suggest invoice no if empty (or still placeholder).
        if not self.inv_no.text().strip():
            try:
                inv_date_iso = datetime.strptime(self.inv_date.text().strip(), "%d.%m.%Y").date()
            except Exception:
                inv_date_iso = date.today()
            n = self._repo.get_next_invoice_serial(inv_date_iso)
            self.inv_no.setText(f"{n:03d}")

    def _toggle_ship_fields(self) -> None:
        enabled = not self.ship_same.isChecked()
        for w in (self.ship_name, self.ship_address, self.ship_gstin, self.ship_state, self.ship_state_code):
            w.setEnabled(enabled)

    def _generate(self) -> None:
        if self.customer_cb.currentIndex() <= 0:
            QMessageBox.warning(self, "Missing", "Please add/import customers first.")
            return

        template_path = self._repo.get_setting("invoice_template_path", "").strip()
        output_folder = self._repo.get_setting("invoice_output_folder", "").strip()
        if not template_path:
            QMessageBox.warning(self, "Missing", "Please set the invoice template path in Settings.")
            return
        if not output_folder:
            QMessageBox.warning(self, "Missing", "Please set the invoice output folder in Settings.")
            return

        tpl = Path(template_path)
        if not tpl.is_file():
            QMessageBox.warning(
                self,
                "Missing",
                f"Invoice template file does not exist:\n{tpl}",
            )
            return

        try:
            invoice_no = self.inv_no.text().strip()
            if not invoice_no:
                raise ValueError("Invoice no is required")
            if not invoice_no.isdigit():
                raise ValueError("Invoice no must be numeric (e.g. 001)")
            inv_date_str = self.inv_date.text().strip()
            # validate
            datetime.strptime(inv_date_str, "%d.%m.%Y")
        except Exception as e:
            QMessageBox.warning(self, "Invalid", str(e))
            return

        customer_id = int(self.customer_cb.currentData())
        customer_name = self.cust_name.text().strip() or str(self.customer_cb.currentText()).strip()

        lines: list[InvoiceLine] = []
        for i, entry in enumerate(self.item_rows):
            desc = self._invoice_line_description(entry).strip()
            if not desc:
                continue
            hsn = entry["hsn"].text().strip()
            unit = entry["unit"].text().strip() or "Kgs"
            qty_s = entry["qty"].text().strip()
            rate_s = entry["rate"].text().strip()
            try:
                qty = float(qty_s)
                rate = float(rate_s)
            except Exception:
                QMessageBox.warning(self, "Invalid", f"Line {i+1}: Qty/Rate must be numbers.")
                return
            lines.append(InvoiceLine(description=desc, hsn=hsn, qty=qty, unit=unit, rate=rate))

        if not lines:
            QMessageBox.warning(self, "Missing", "Please enter at least one product line.")
            return

        line_chk = 0
        for entry in self.item_rows:
            desc = self._invoice_line_description(entry).strip()
            if not desc:
                continue
            line_chk += 1
            item_id = self._resolve_item_id_from_combo(entry["item_cb"])
            braw = entry["batch_cb"].currentData()
            bid = int(braw) if braw is not None else None
            if bid is not None:
                if item_id is None:
                    QMessageBox.warning(
                        self,
                        "Batch link",
                        f"Line {line_chk}: pick the product from the dropdown (not only free-typed text) "
                        "to link a production batch, or set Batch to “— none —”.",
                    )
                    return
                b = self._repo.get_production_batch(bid)
                if b is None:
                    QMessageBox.warning(
                        self,
                        "Batch link",
                        f"Line {line_chk}: selected batch no longer exists. Refresh and pick again.",
                    )
                    return
                if int(b["product_item_id"]) != item_id:
                    QMessageBox.warning(
                        self,
                        "Batch link",
                        f"Line {line_chk}: that batch is for a different product than this line.",
                    )
                    return

        fg_err = self._invoice_fg_stock_plan_error()
        if fg_err:
            QMessageBox.warning(self, "Finished-goods stock", fg_err)
            return

        safe_customer = _safe_filename(customer_name)
        out_path = Path(output_folder) / f"Inv {invoice_no} {safe_customer}.xlsx"

        # Preview (invoice-like safety step)
        subtotal, est_gst, est_total = compute_gst_invoice_totals(lines)
        amount_words = _number_to_words(float(est_total))

        def _esc(s: str) -> str:
            return (
                (s or "")
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\n", "<br>")
            )

        bill_name = format_invoice_customer_display_name(
            self.cust_name.text().strip() or customer_name
        )
        bill_addr = self.cust_address.toPlainText().strip()
        bill_gstin = self.cust_gstin.text().strip()
        bill_state = self.cust_state.text().strip()
        bill_code = self.cust_state_code.text().strip()

        ship_same = self.ship_same.isChecked()
        ship_name = (
            bill_name
            if ship_same
            else format_invoice_customer_display_name(self.ship_name.text().strip())
        )
        ship_addr = bill_addr if ship_same else self.ship_address.toPlainText().strip()
        ship_gstin = bill_gstin if ship_same else self.ship_gstin.text().strip()
        ship_state = bill_state if ship_same else self.ship_state.text().strip()
        ship_code = bill_code if ship_same else self.ship_state_code.text().strip()

        ship_empty_note = ""
        if not ship_same and not any((ship_name, ship_addr, ship_gstin, ship_state, ship_code)):
            ship_empty_note = (
                '<div style="margin-top:10px; color:#777; font-style:italic; font-size:12px;">'
                "No ship-to details entered. Either fill the Ship fields "
                "or tick “Shipped To same as Billed To”.</div>"
            )

        td = "padding:8px 14px; border-bottom:1px solid #eee; line-height:1.45;"

        items_rows_html = ""
        for i, ln in enumerate(lines, start=1):
            items_rows_html += (
                "<tr>"
                f"<td style='{td} width:40px;'>{i}</td>"
                f"<td style='{td}'>{_esc(ln.description)}</td>"
                f"<td style='{td} width:100px;'>{_esc(ln.hsn)}</td>"
                f"<td style='{td} text-align:right; width:72px;'>{ln.qty:g}</td>"
                f"<td style='{td} width:64px;'>{_esc(ln.unit)}</td>"
                f"<td style='{td} text-align:right; width:96px;'>{ln.rate:,.2f}</td>"
                "</tr>"
            )

        other_block = f"""
            <div style="font-weight:700; margin-bottom:10px; font-size:13px;">Other details</div>
            <div style="padding-left:16px; color:#333; line-height:1.75;">
              <div>Transport mode:&nbsp;&nbsp;{_esc(self.transport.text().strip())}</div>
              <div>E-way bill no:&nbsp;&nbsp;&nbsp;&nbsp;{_esc(self.eway.text().strip())}</div>
              <div>Payment terms:&nbsp;&nbsp;{_esc(self.payment_terms.text().strip())}</div>
              <div>Place of supply:&nbsp;&nbsp;{_esc(self.place_supply.text().strip())}</div>
              <div>P.O. no / date:&nbsp;&nbsp;&nbsp;{_esc(self.po_no.text().strip())}
                &nbsp;&nbsp;|&nbsp;&nbsp;{_esc(self.po_date.text().strip())}</div>
            </div>
        """

        html = f"""
        <div style="font-family:Segoe UI, Arial; font-size:12.5px; padding:4px 8px; line-height:1.5;">
          <div style="margin-bottom:18px;">
            <div style="font-size:18px; font-weight:700; letter-spacing:0.3px;">Tax Invoice (Preview)</div>
            <div style="margin-top:8px; padding-left:4px; color:#444;">
              Invoice no:&nbsp;&nbsp;<b>{_esc(invoice_no)}</b>
              &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Date:&nbsp;&nbsp;<b>{_esc(inv_date_str)}</b>
            </div>
          </div>

          <div style="display:flex; gap:18px; margin-bottom:20px;">
            <div style="flex:1; border:1px solid #ddd; padding:14px 16px; border-radius:6px;">
              <div style="font-weight:700; margin-bottom:10px; font-size:13px;">Billed To</div>
              <div style="padding-left:12px; color:#222;">
                <div style="margin-bottom:6px;"><b>{_esc(bill_name)}</b></div>
                <div style="color:#333; white-space:pre-wrap;">{_esc(bill_addr)}</div>
                <div style="margin-top:8px;">GSTIN:&nbsp;&nbsp;{_esc(bill_gstin)}</div>
                <div>State:&nbsp;&nbsp;{_esc(bill_state)}&nbsp;&nbsp;&nbsp;&nbsp;Code:&nbsp;&nbsp;{_esc(bill_code)}</div>
              </div>
            </div>
            <div style="flex:1; border:1px solid #ddd; padding:14px 16px; border-radius:6px;">
              <div style="font-weight:700; margin-bottom:10px; font-size:13px;">Shipped To</div>
              <div style="padding-left:12px; color:#222;">
                <div style="margin-bottom:6px;"><b>{_esc(ship_name)}</b></div>
                <div style="color:#333; white-space:pre-wrap;">{_esc(ship_addr)}</div>
                <div style="margin-top:8px;">GSTIN:&nbsp;&nbsp;{_esc(ship_gstin)}</div>
                <div>State:&nbsp;&nbsp;{_esc(ship_state)}&nbsp;&nbsp;&nbsp;&nbsp;Code:&nbsp;&nbsp;{_esc(ship_code)}</div>
                {ship_empty_note}
              </div>
            </div>
          </div>

          <div style="border:1px solid #ddd; padding:14px 16px; border-radius:6px; margin-bottom:20px;">
            {other_block}
          </div>

          <div style="font-weight:700; margin-bottom:10px; font-size:13px; padding-left:2px;">Products</div>
          <div style="border:1px solid #ddd; border-radius:6px; overflow:hidden;">
            <table style="border-collapse:collapse; width:100%;">
              <thead>
                <tr style="background:#f6f6f6;">
                  <th style="text-align:left; padding:10px 14px; width:40px;">#</th>
                  <th style="text-align:left; padding:10px 14px;">Product</th>
                  <th style="text-align:left; padding:10px 14px; width:100px;">HSN</th>
                  <th style="text-align:right; padding:10px 14px; width:72px;">Qty</th>
                  <th style="text-align:left; padding:10px 14px; width:64px;">Unit</th>
                  <th style="text-align:right; padding:10px 14px; width:96px;">Rate</th>
                </tr>
              </thead>
              <tbody>
                {items_rows_html}
              </tbody>
            </table>
          </div>

          <div style="height:18px;"></div>

          <div style="display:flex; justify-content:flex-end;">
            <div style="width:360px; border:1px solid #ddd; padding:14px 18px; border-radius:6px;">
              <div style="font-weight:700; margin-bottom:12px; font-size:13px;">Totals</div>
              <table style="width:100%; border-collapse:collapse; font-size:13px;">
                <tr>
                  <td style="padding:6px 4px; vertical-align:baseline;">Subtotal</td>
                  <td style="padding:6px 4px; text-align:right; vertical-align:baseline;"><b>{subtotal:,.2f}</b></td>
                </tr>
                <tr>
                  <td style="padding:6px 4px; vertical-align:baseline;">GST (18%)</td>
                  <td style="padding:6px 4px; text-align:right; vertical-align:baseline;"><b>{est_gst:,.2f}</b></td>
                </tr>
                <tr style="font-size:14px;">
                  <td style="padding:8px 4px 6px; vertical-align:baseline; font-weight:600;">Grand total</td>
                  <td style="padding:8px 4px 6px; text-align:right; vertical-align:baseline;"><b>{est_total:,.2f}</b></td>
                </tr>
              </table>
              <div style="margin-top:12px; padding-top:10px; border-top:1px solid #eee; color:#333; font-size:11.5px; line-height:1.6;">
                <div style="margin-bottom:4px;">Amount in words</div>
                <b>{_esc(amount_words)}</b>
              </div>
            </div>
          </div>
        </div>
        """

        dlg = QDialog(self)
        dlg.setWindowTitle("Invoice Preview")
        dlg.resize(920, 720)
        v = QVBoxLayout(dlg)
        preview = QTextEdit()
        preview.setReadOnly(True)
        preview.setHtml(html)
        v.addWidget(preview, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Generate .xlsx")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Back")
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        v.addWidget(buttons)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            total, saved_path = generate_invoice_excel(
                GenerateInvoiceInput(
                    template_path=Path(template_path),
                    output_path=out_path,
                    invoice_no=invoice_no,
                    invoice_date_ddmmyyyy=inv_date_str,
                    customer_name=customer_name,
                    customer_address=self.cust_address.toPlainText().strip(),
                    customer_gstin=self.cust_gstin.text().strip(),
                    customer_state=self.cust_state.text().strip(),
                    customer_state_code=self.cust_state_code.text().strip(),
                    transport_mode=self.transport.text().strip(),
                    eway_bill_no=self.eway.text().strip(),
                    payment_terms=self.payment_terms.text().strip(),
                    place_of_supply=self.place_supply.text().strip(),
                    po_no=self.po_no.text().strip(),
                    po_date=self.po_date.text().strip(),
                    shipped_same_as_billed=self.ship_same.isChecked(),
                    ship_name=self.ship_name.text().strip(),
                    ship_address=self.ship_address.toPlainText().strip(),
                    ship_gstin=self.ship_gstin.text().strip(),
                    ship_state=self.ship_state.text().strip(),
                    ship_state_code=self.ship_state_code.text().strip(),
                    lines=lines,
                )
            )
        except Exception as e:
            QMessageBox.critical(self, "Invoice file error", str(e))
            return

        # Store in DB (for dues/ledger + line-level batch link for costing)
        try:
            inv_date_iso = datetime.strptime(inv_date_str, "%d.%m.%Y").date()
            with transaction(self._repo.conn):
                invoice_id = self._repo.create_invoice(
                    customer_id=customer_id,
                    invoice_no=invoice_no,
                    invoice_date=inv_date_iso,
                    total_after_tax=float(total),
                    excel_path=saved_path,
                )
                db_lines: list[dict] = []
                ln = 0
                for entry in self.item_rows:
                    desc = self._invoice_line_description(entry).strip()
                    if not desc:
                        continue
                    ln += 1
                    hsn = entry["hsn"].text().strip()
                    unit = entry["unit"].text().strip() or "Kgs"
                    qty = float(entry["qty"].text().strip())
                    rate = float(entry["rate"].text().strip())
                    amount = qty * rate
                    pbid = None
                    braw = entry["batch_cb"].currentData()
                    if braw is not None:
                        pbid = int(braw)
                    item_id = self._resolve_item_id_from_combo(entry["item_cb"])
                    row = {
                        "line_no": ln,
                        "description": desc,
                        "hsn": hsn,
                        "qty": qty,
                        "unit": unit,
                        "rate": rate,
                        "amount": amount,
                        "production_batch_id": pbid,
                    }
                    if item_id is not None:
                        row["product_item_id"] = int(item_id)
                    db_lines.append(row)
                if db_lines:
                    self._repo.add_invoice_items(invoice_id, db_lines)
        except Exception as e:
            msg = str(e)
            if "UNIQUE constraint failed" in msg and "invoice_no" in msg:
                msg = (
                    f"This invoice number is already used in the ledger.\n\n{msg}\n\n"
                    "Choose a different invoice number or remove the duplicate from the database."
                )
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle("Saved Excel, DB warning")
            box.setText(f"Excel saved at:\n{saved_path}\n\nBut DB insert failed:\n{msg}")
            ob = box.addButton("Open Excel", QMessageBox.ButtonRole.ActionRole)
            box.addButton(QMessageBox.StandardButton.Ok)
            box.exec()
            if box.clickedButton() == ob:
                ok, err = open_local_file(str(saved_path))
                if not ok:
                    QMessageBox.warning(self, "Open file", err)
            return

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Success")
        box.setText(f"Invoice saved:\n{saved_path}\n\nGrand total: {total:,.2f}")
        ob = box.addButton("Open Excel", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if box.clickedButton() == ob:
            ok, err = open_local_file(str(saved_path))
            if not ok:
                QMessageBox.warning(self, "Open file", err)
        self.created.emit()
        self._suggest_next_invoice_no()
        self._update_generate_enabled()

