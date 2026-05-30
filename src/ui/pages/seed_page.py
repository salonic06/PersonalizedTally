from __future__ import annotations

from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...db.conn import transaction
from ...excel_import import iter_invoice_excels, read_invoice_from_excel
from ...repo import Repo, normalize_rm_short_code
from ..form_util import (
    configure_form,
    form_add_row,
    form_add_title_row,
    form_add_widget_row,
    form_hint,
    form_label,
)
from ..page_header import make_page_header


class SeedPage(QWidget):
    data_changed = Signal()

    """
    Temporary page to quickly add customers + invoices so Phase 1 (dues/payments) is testable.
    We'll replace this with proper Customer/Invoice modules later.
    """

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

        scroll_inner = QWidget()
        layout = QVBoxLayout(scroll_inner)
        scroll.setWidget(scroll_inner)

        layout.addWidget(
            make_page_header(
                "Setup (Seed Data)",
                "Masters, bulk invoice import, and demo fixtures — owner only.",
            )
        )

        # --- Customer ---
        cust_box = QFrame()
        cust_box.setObjectName("formCard")
        cust_form = QFormLayout(cust_box)
        configure_form(cust_form)
        form_add_title_row(cust_form, "Add / Update Customer")

        self.cust_pick = QComboBox()
        self.cust_pick.setMinimumHeight(32)
        form_add_row(cust_form, "Select (optional)", self.cust_pick)

        self.cust_name = QLineEdit()
        self.cust_name.setPlaceholderText("Customer name")
        self.cust_name.setMinimumHeight(32)
        form_add_row(cust_form, "Name", self.cust_name)

        self.cust_credit = QLineEdit()
        self.cust_credit.setPlaceholderText("45")
        self.cust_credit.setText("45")
        self.cust_credit.setMinimumHeight(32)
        self.cust_state = QLineEdit()
        self.cust_state.setMinimumHeight(32)

        cd_state_row = QHBoxLayout()
        cd_state_row.addWidget(form_label("Credit days"), 0)
        cd_state_row.addWidget(self.cust_credit, 1)
        cd_state_row.addWidget(form_label("State"), 0)
        cd_state_row.addWidget(self.cust_state, 1)
        form_add_widget_row(cust_form, cd_state_row)

        self.cust_state_code = QLineEdit()
        self.cust_state_code.setMinimumHeight(32)
        self.cust_gstin = QLineEdit()
        self.cust_gstin.setMinimumHeight(32)
        sc_gst_row = QHBoxLayout()
        sc_gst_row.addWidget(form_label("State code"), 0)
        sc_gst_row.addWidget(self.cust_state_code, 1)
        sc_gst_row.addWidget(form_label("GSTIN"), 0)
        sc_gst_row.addWidget(self.cust_gstin, 2)
        form_add_widget_row(cust_form, sc_gst_row)

        self.cust_address = QLineEdit()
        self.cust_address.setMinimumHeight(32)
        form_add_row(cust_form, "Address", self.cust_address)

        self.btn_save_cust = QPushButton("Save Customer")
        self.btn_save_cust.setMinimumHeight(34)
        form_add_widget_row(cust_form, self.btn_save_cust)
        self.btn_trash_cust = QPushButton("Move selected customer to trash…")
        self.btn_trash_cust.setMinimumHeight(34)
        form_add_widget_row(cust_form, self.btn_trash_cust)
        layout.addWidget(cust_box)

        # --- Products master (quick add); DB table remains `items`. ---
        item_box = QFrame()
        item_box.setObjectName("formCard")
        item_form = QFormLayout(item_box)
        configure_form(item_form)
        form_add_title_row(item_form, "Products master (quick add)")

        self.item_name = QLineEdit()
        self.item_name.setMinimumHeight(32)
        form_add_row(item_form, "Product name", self.item_name)

        self.item_hsn = QLineEdit()
        self.item_hsn.setMinimumHeight(32)
        self.item_unit = QLineEdit()
        self.item_unit.setMinimumHeight(32)
        self.item_unit.setText("Kgs")
        hsn_unit_row = QHBoxLayout()
        hsn_unit_row.addWidget(form_label("HSN"), 0)
        hsn_unit_row.addWidget(self.item_hsn, 1)
        hsn_unit_row.addWidget(form_label("Unit"), 0)
        hsn_unit_row.addWidget(self.item_unit, 1)
        form_add_widget_row(item_form, hsn_unit_row)

        self.item_rate = QLineEdit()
        self.item_rate.setMinimumHeight(32)
        self.item_rate.setPlaceholderText("Default rate (optional)")
        form_add_row(item_form, "Default rate", self.item_rate)

        self.btn_save_item = QPushButton("Save product")
        self.btn_save_item.setMinimumHeight(34)
        form_add_widget_row(item_form, self.btn_save_item)
        self.btn_trash_item = QPushButton("Move product to trash (uses Product name field)…")
        self.btn_trash_item.setMinimumHeight(34)
        form_add_widget_row(item_form, self.btn_trash_item)
        layout.addWidget(item_box)

        # --- Raw materials master (with products; not on stock screen) ---
        rm_box = QFrame()
        rm_box.setObjectName("formCard")
        rm_form = QFormLayout(rm_box)
        configure_form(rm_form)
        form_add_title_row(rm_form, "Raw materials master")
        form_add_widget_row(
            rm_form,
            form_hint(
                "Define codes, names, unit, and type here. The Raw materials & stock page only shows codes, "
                "types, and quantities — use this screen for confidential naming. "
                "Type is a drop-down of types already used on other RMs (empty until you save some); "
                "you can also type a new type."
            ),
        )

        self.rm_pick = QComboBox()
        self.rm_pick.setMinimumHeight(32)
        form_add_row(rm_form, "Select (optional)", self.rm_pick)

        self.rm_code = QLineEdit()
        self.rm_code.setMinimumHeight(32)
        form_add_row(rm_form, "RM code", self.rm_code)

        self.rm_name = QLineEdit()
        self.rm_name.setMinimumHeight(32)
        form_add_row(rm_form, "Name", self.rm_name)

        self.rm_unit = QLineEdit()
        self.rm_unit.setText("Kg")
        self.rm_unit.setMinimumHeight(32)
        self.rm_type = QComboBox()
        self.rm_type.setEditable(True)
        self.rm_type.setMinimumHeight(32)
        self.rm_type.setToolTip("Pick an existing type or type a new one. List fills from types already saved on RMs.")

        unit_sec_row = QHBoxLayout()
        unit_sec_row.addWidget(form_label("Unit"), 0)
        unit_sec_row.addWidget(self.rm_unit, 1)
        unit_sec_row.addWidget(form_label("Type"), 0)
        unit_sec_row.addWidget(self.rm_type, 2)
        form_add_widget_row(rm_form, unit_sec_row)

        self.rm_reorder = QDoubleSpinBox()
        self.rm_reorder.setDecimals(2)
        self.rm_reorder.setMaximum(1e12)
        self.rm_reorder.setMinimum(0.0)
        self.rm_reorder.setSpecialValueText("—")
        self.rm_reorder.setMinimum(-1.0)
        self.rm_reorder.setValue(-1.0)
        self.rm_reorder.setMinimumHeight(32)
        self.rm_reorder.setToolTip("Optional: flag when on-hand stock falls below this quantity (same unit as RM).")
        form_add_row(rm_form, "Reorder level (optional)", self.rm_reorder)

        self.rm_product_link = QComboBox()
        self.rm_product_link.setMinimumHeight(32)
        self.rm_product_link.setMinimumWidth(260)
        self.rm_product_link.setToolTip(
            "Use for finished-goods stock rows (e.g. RM code LP750 for sellable product Lampol 750). "
            "When set, saving batch yield adds quantity here; invoicing with that batch reduces it."
        )
        form_add_row(rm_form, "Finished-good stock for product", self.rm_product_link)

        self.btn_save_rm = QPushButton("Save raw material")
        self.btn_save_rm.setMinimumHeight(34)
        form_add_widget_row(rm_form, self.btn_save_rm)
        self.btn_trash_rm = QPushButton("Move selected RM to trash…")
        self.btn_trash_rm.setMinimumHeight(34)
        form_add_widget_row(rm_form, self.btn_trash_rm)
        layout.addWidget(rm_box)

        # --- Import (migration only) ---
        imp_box = QFrame()
        imp_box.setObjectName("formCard")
        imp_form = QFormLayout(imp_box)
        configure_form(imp_form)
        form_add_title_row(imp_form, "Import Existing Excel Invoices (one-time migration)")

        self.imp_folder = QLineEdit()
        self.imp_folder.setMinimumHeight(32)
        self.imp_folder.setPlaceholderText("Folder containing historical invoice Excel files…")

        pick_row = QHBoxLayout()
        pick_row.addWidget(self.imp_folder, 1)
        self.btn_pick = QPushButton("Choose Folder…")
        self.btn_pick.setMinimumHeight(32)
        pick_row.addWidget(self.btn_pick)
        form_add_row(imp_form, "Folder", pick_row)

        self.btn_import = QPushButton("Import invoices from folder")
        self.btn_import.setMinimumHeight(34)
        form_add_widget_row(imp_form, self.btn_import)
        form_add_widget_row(
            imp_form,
            form_hint("Note: once you start generating invoices from the app, you won't need this."),
        )
        layout.addWidget(imp_box)

        layout.addStretch(1)

        self.btn_save_cust.clicked.connect(self._save_customer)
        self.btn_trash_cust.clicked.connect(self._trash_customer)
        self.btn_save_item.clicked.connect(self._save_item)
        self.btn_trash_item.clicked.connect(self._trash_item)
        self.btn_pick.clicked.connect(self._pick_folder)
        self.btn_import.clicked.connect(self._import_folder)
        self.cust_pick.currentIndexChanged.connect(self._load_selected_customer)
        self.rm_pick.currentIndexChanged.connect(self._load_selected_rm)
        self.btn_save_rm.clicked.connect(self._save_rm)
        self.btn_trash_rm.clicked.connect(self._trash_rm)
        self.reload_customers()
        self.reload_rm_pick()

    def _reload_rm_type_combo(self, preset: str = "") -> None:
        preset = (preset or "").strip()
        self.rm_type.blockSignals(True)
        self.rm_type.clear()
        self.rm_type.addItem("")
        for t in self._repo.list_distinct_rm_types():
            self.rm_type.addItem(t)
        self.rm_type.blockSignals(False)
        if not preset:
            self.rm_type.setCurrentIndex(0)
            return
        ix = self.rm_type.findText(preset)
        if ix >= 0:
            self.rm_type.setCurrentIndex(ix)
        else:
            self.rm_type.setEditText(preset)

    def reload_customers(self) -> None:
        current_id = self.cust_pick.currentData()
        self.cust_pick.clear()
        self.cust_pick.addItem("", None)
        for c in self._repo.list_customers():
            self.cust_pick.addItem(str(c["name"]), int(c["id"]))
        if current_id is not None:
            idx = self.cust_pick.findData(current_id)
            if idx >= 0:
                self.cust_pick.setCurrentIndex(idx)

    def _reload_rm_product_combo(self, preset_product_id: int | None) -> None:
        self.rm_product_link.blockSignals(True)
        self.rm_product_link.clear()
        self.rm_product_link.addItem("(not linked — RM only)", None)
        for it in self._repo.list_items():
            self.rm_product_link.addItem(str(it["name"]), int(it["id"]))
        if preset_product_id is not None:
            ix = self.rm_product_link.findData(preset_product_id)
            self.rm_product_link.setCurrentIndex(ix if ix >= 0 else 0)
        else:
            self.rm_product_link.setCurrentIndex(0)
        self.rm_product_link.blockSignals(False)

    def reload_rm_pick(self) -> None:
        current_id = self.rm_pick.currentData()
        self.rm_pick.blockSignals(True)
        self.rm_pick.clear()
        self.rm_pick.addItem("", None)
        for r in self._repo.list_raw_materials():
            self.rm_pick.addItem(str(r["short_code"]), int(r["id"]))
        self.rm_pick.blockSignals(False)
        if current_id is not None:
            idx = self.rm_pick.findData(current_id)
            if idx >= 0:
                self.rm_pick.setCurrentIndex(idx)
                self._load_selected_rm()
                return
        self.rm_code.clear()
        self.rm_name.clear()
        self.rm_unit.setText("Kg")
        self.rm_reorder.setValue(-1.0)
        self._reload_rm_type_combo("")
        self._reload_rm_product_combo(None)

    def _load_selected_rm(self) -> None:
        rid = self.rm_pick.currentData()
        if not rid:
            self.rm_code.clear()
            self.rm_name.clear()
            self.rm_unit.setText("Kg")
            self.rm_reorder.setValue(-1.0)
            self._reload_rm_type_combo("")
            self._reload_rm_product_combo(None)
            return
        r = self._repo.get_raw_material(int(rid))
        if not r:
            return
        self.rm_code.setText(str(r["short_code"] or ""))
        self.rm_name.setText(str(r["name"] or ""))
        self.rm_unit.setText(str(r["unit"] or "Kg"))
        typ = str(r["rm_type"] or "").strip()
        self._reload_rm_type_combo(typ)
        rl = r["reorder_level"]
        if rl is None:
            self.rm_reorder.setValue(-1.0)
        else:
            self.rm_reorder.setValue(float(rl))
        pid = r["product_item_id"]
        pidi = int(pid) if pid is not None else None
        self._reload_rm_product_combo(pidi)

    def _save_rm(self) -> None:
        try:
            sc = normalize_rm_short_code(self.rm_code.text())
        except ValueError as e:
            QMessageBox.warning(self, "RM code", str(e))
            return
        name = self.rm_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing", "Name is required.")
            return
        u = self.rm_unit.text().strip() or "Kg"
        typ_txt = self.rm_type.currentText().strip()
        material_type = typ_txt or None
        rl = None if self.rm_reorder.value() < 0 else float(self.rm_reorder.value())
        pick_id = self.rm_pick.currentData()
        plink = self.rm_product_link.currentData()
        product_item_id = int(plink) if plink is not None else None
        try:
            with transaction(self._repo.conn):
                if pick_id:
                    self._repo.update_raw_material(
                        int(pick_id),
                        name=name,
                        short_code=sc,
                        unit=u,
                        material_type=material_type,
                        reorder_level=rl,
                        product_item_id=product_item_id,
                    )
                else:
                    self._repo.add_raw_material(
                        name,
                        sc,
                        unit=u,
                        material_type=material_type,
                        reorder_level=rl,
                        product_item_id=product_item_id,
                    )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.reload_rm_pick()
        QMessageBox.information(self, "Saved", "Raw material saved.")
        self.data_changed.emit()

    def _trash_rm(self) -> None:
        rid = self.rm_pick.currentData()
        if not rid:
            QMessageBox.information(self, "Trash", "Select an RM in the dropdown first.")
            return
        code = self.rm_pick.currentText()
        if (
            QMessageBox.question(
                self,
                "Confirm",
                f"Move RM “{code}” to trash? Restore from the Trash page if needed. "
                f"Only allowed when on-hand stock is zero.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            with transaction(self._repo.conn):
                self._repo.soft_delete_raw_material(int(rid))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.rm_pick.setCurrentIndex(0)
        self.rm_code.clear()
        self.rm_name.clear()
        self.rm_unit.setText("Kg")
        self.rm_reorder.setValue(-1.0)
        self.reload_rm_pick()
        QMessageBox.information(self, "Trash", "Raw material moved to trash.")
        self.data_changed.emit()

    def _load_selected_customer(self) -> None:
        cid = self.cust_pick.currentData()
        if not cid:
            return
        c = self._repo.get_customer(int(cid))
        if not c:
            return
        self.cust_name.setText(str(c["name"] or ""))
        self.cust_credit.setText(str(c["credit_days"] or "45"))
        self.cust_gstin.setText(str(c["gstin"] or ""))
        self.cust_state.setText(str(c["state"] or ""))
        self.cust_state_code.setText(str(c["state_code"] or ""))
        self.cust_address.setText(str(c["address"] or ""))

    def _save_customer(self) -> None:
        try:
            with transaction(self._repo.conn):
                cid = self.cust_pick.currentData()
                name = self.cust_name.text().strip()
                credit_days = int(self.cust_credit.text().strip() or "45")
                if cid:
                    self._repo.update_customer_details(
                        int(cid),
                        name=name,
                        credit_days=credit_days,
                        gstin=self.cust_gstin.text(),
                        state=self.cust_state.text(),
                        state_code=self.cust_state_code.text(),
                        address=self.cust_address.text(),
                    )
                else:
                    self._repo.upsert_customer(name=name, credit_days=credit_days)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self.cust_name.clear()
        self.cust_gstin.clear()
        self.cust_state.clear()
        self.cust_state_code.clear()
        self.cust_address.clear()
        self.reload_customers()
        QMessageBox.information(self, "Saved", "Customer saved.")
        self.data_changed.emit()

    def _trash_customer(self) -> None:
        cid = self.cust_pick.currentData()
        if not cid:
            QMessageBox.information(self, "Trash", "Select a customer in the dropdown first.")
            return
        name = self.cust_name.text().strip() or self.cust_pick.currentText()
        if (
            QMessageBox.question(
                self,
                "Confirm",
                f"Move customer “{name}” to trash? They will disappear from lists until restored "
                f"(Trash page). Invoices and payments for this customer remain in the database.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            with transaction(self._repo.conn):
                self._repo.soft_delete_customer(int(cid))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.cust_pick.setCurrentIndex(0)
        self.cust_name.clear()
        self.reload_customers()
        QMessageBox.information(self, "Trash", "Customer moved to trash.")
        self.data_changed.emit()

    def _save_item(self) -> None:
        try:
            name = self.item_name.text().strip()
            hsn = self.item_hsn.text().strip()
            unit = self.item_unit.text().strip()
            rate_txt = self.item_rate.text().strip()
            rate = None if not rate_txt else float(rate_txt)
            with transaction(self._repo.conn):
                self._repo.upsert_item(name=name, hsn=hsn, unit=unit, default_rate=rate)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self.item_name.clear()
        self.item_hsn.clear()
        self.item_rate.clear()
        QMessageBox.information(self, "Saved", "Product saved.")
        self.data_changed.emit()
        cur = self.rm_product_link.currentData()
        self._reload_rm_product_combo(int(cur) if cur is not None else None)

    def _trash_item(self) -> None:
        name = self.item_name.text().strip()
        if not name:
            QMessageBox.information(self, "Trash", "Enter the product name to trash.")
            return
        row = self._repo.conn.execute(
            "SELECT id FROM items WHERE name = ? AND is_deleted = 0", (name,)
        ).fetchone()
        if row is None:
            QMessageBox.information(self, "Trash", f"No active product named “{name}”.")
            return
        if (
            QMessageBox.question(
                self,
                "Confirm",
                f"Move product “{name}” to trash? Restore from the Trash page if needed.",
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            with transaction(self._repo.conn):
                self._repo.soft_delete_item(int(row["id"]))
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return
        self.item_name.clear()
        QMessageBox.information(self, "Trash", "Product moved to trash.")
        self.data_changed.emit()
        cur = self.rm_product_link.currentData()
        self._reload_rm_product_combo(int(cur) if cur is not None else None)

    def _pick_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select folder containing Excel invoices")
        if folder:
            self.imp_folder.setText(folder)

    def _import_folder(self) -> None:
        folder = Path(self.imp_folder.text().strip())
        if not folder.exists():
            QMessageBox.warning(self, "Missing", "Folder not found.")
            return

        imported = 0
        skipped = 0
        errors: list[str] = []

        with transaction(self._repo.conn):
            for path in iter_invoice_excels(folder):
                try:
                    inv = read_invoice_from_excel(path)
                    customer_id = self._repo.upsert_customer(inv.customer_name, credit_days=45)
                    # Also save customer details from Excel.
                    # If shipping and billing details match (common), prefer shipping details when present.
                    def _same(a: str, b: str) -> bool:
                        return " ".join((a or "").split()).strip().lower() == " ".join((b or "").split()).strip().lower()

                    ship_same = False
                    if inv.ship_address or inv.ship_gstin or inv.ship_state or inv.ship_state_code:
                        ship_same = _same(inv.customer_name, inv.ship_name or inv.customer_name) and _same(
                            inv.customer_address, inv.ship_address or inv.customer_address
                        )

                    addr = inv.ship_address if (ship_same and inv.ship_address) else inv.customer_address
                    gst = inv.ship_gstin if (ship_same and inv.ship_gstin) else inv.customer_gstin
                    state = inv.ship_state if (ship_same and inv.ship_state) else inv.customer_state
                    code = inv.ship_state_code if (ship_same and inv.ship_state_code) else inv.customer_state_code

                    self._repo.update_customer_details(
                        customer_id,
                        name=inv.customer_name,
                        credit_days=45,
                        gstin=gst,
                        state=state,
                        state_code=code,
                        address=addr,
                    )
                    invoice_id = self._repo.create_invoice(
                        customer_id=customer_id,
                        invoice_no=inv.invoice_no,
                        invoice_date=inv.invoice_date,
                        total_after_tax=inv.total_after_tax,
                        excel_path=inv.excel_path,
                    )
                    # Store items for future analytics/costing.
                    if inv.lines:
                        self._repo.add_invoice_items(invoice_id, inv.lines)
                    imported += 1
                except Exception as e:
                    msg = str(e)
                    # Likely duplicate invoice_no: treat as skip, not fatal.
                    if "UNIQUE constraint failed: invoices.invoice_no" in msg:
                        skipped += 1
                        continue
                    errors.append(f"{path.name}: {msg}")

        self.reload_customers()
        self.data_changed.emit()

        summary = f"Imported: {imported}\\nSkipped (duplicates): {skipped}"
        if errors:
            summary += f"\\nErrors: {len(errors)}\\n\\n" + "\\n".join(errors[:10])
            if len(errors) > 10:
                summary += f"\\n... and {len(errors) - 10} more"
        QMessageBox.information(self, "Import complete", summary)

