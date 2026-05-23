from __future__ import annotations

from calendar import monthrange
from datetime import date

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import QHeaderView
from PySide6.QtWidgets import (
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
)

from ...db.conn import transaction
from ...open_file import open_local_file
from ...repo import Repo
from ...safe_delete import delete_invoice_excel_if_allowed
from ..page_header import make_page_header
from ..trash_invoice_dialog import (
    TrashInvoiceChoice,
    confirm_invoice_permanent_delete,
    confirm_trash_invoice,
)


def _default_due_date_range(today: date) -> tuple[date, date]:
    """First day of current calendar month through last day of next calendar month."""
    start = date(today.year, today.month, 1)
    if today.month == 12:
        ny, nm = today.year + 1, 1
    else:
        ny, nm = today.year, today.month + 1
    end_dom = monthrange(ny, nm)[1]
    end = date(ny, nm, end_dom)
    return start, end


class _SortItem(QTableWidgetItem):
    def __lt__(self, other: QTableWidgetItem) -> bool:  # type: ignore[override]
        for role in (Qt.UserRole + 2, Qt.UserRole):
            a = self.data(role)
            b = other.data(role)
            if a is not None and b is not None:
                try:
                    return a < b
                except Exception:
                    return str(a) < str(b)
        return super().__lt__(other)


class DuePage(QWidget):
    data_changed = Signal()

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo
        self._filter = "all"  # all|due_today|overdue
        self._view = "invoice"  # invoice|customer

        layout = QVBoxLayout(self)
        layout.addWidget(
            make_page_header(
                "Due / Outstanding",
                "Open invoice balances by due date; switch to customer totals or filter overdue / due today.",
            )
        )

        header = QHBoxLayout()
        header.addStretch(1)

        self.view_cb = QComboBox()
        self.view_cb.addItem("Invoice-wise", "invoice")
        self.view_cb.addItem("Customer-wise totals", "customer")
        self.view_cb.setMinimumHeight(32)
        self.view_cb.currentIndexChanged.connect(self._on_view_changed)
        header.addWidget(self.view_cb)

        self.filter_cb = QComboBox()
        self.filter_cb.addItem("All Outstanding", "all")
        self.filter_cb.addItem("Due Today", "due_today")
        self.filter_cb.addItem("Overdue", "overdue")
        self.filter_cb.currentIndexChanged.connect(self._on_filter_changed)
        self.filter_cb.setMinimumHeight(32)
        header.addWidget(self.filter_cb)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setMinimumHeight(32)
        header.addWidget(self.refresh_btn)
        self.refresh_btn.clicked.connect(lambda: self.refresh(today=date.today()))

        layout.addLayout(header)

        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("Due date"))
        self.due_from_de = QDateEdit()
        self.due_from_de.setCalendarPopup(True)
        self.due_from_de.setDisplayFormat("dd-MM-yyyy")
        t = date.today()
        d0, d1 = _default_due_date_range(t)
        self.due_from_de.setDate(QDate(d0.year, d0.month, d0.day))
        self.due_from_de.setMinimumHeight(32)
        range_row.addWidget(self.due_from_de)
        range_row.addWidget(QLabel("to"))
        self.due_to_de = QDateEdit()
        self.due_to_de.setCalendarPopup(True)
        self.due_to_de.setDisplayFormat("dd-MM-yyyy")
        self.due_to_de.setDate(QDate(d1.year, d1.month, d1.day))
        self.due_to_de.setMinimumHeight(32)
        range_row.addWidget(self.due_to_de)
        range_row.addStretch(1)
        layout.addLayout(range_row)

        self.due_from_de.dateChanged.connect(lambda _: self.refresh(today=date.today()))
        self.due_to_de.dateChanged.connect(lambda _: self.refresh(today=date.today()))

        self.summary = QLabel("")
        self.summary.setStyleSheet("color:#333; font-size:13px;")
        layout.addWidget(self.summary)

        act_row = QHBoxLayout()
        self.btn_open_xl = QPushButton("Open invoice Excel")
        self.btn_open_xl.setMinimumHeight(32)
        self.btn_open_xl.setEnabled(False)
        self.btn_open_xl.clicked.connect(self._open_selected_invoice_excel)
        act_row.addWidget(self.btn_open_xl)
        self.btn_trash_inv = QPushButton("Move invoice to trash")
        self.btn_trash_inv.setMinimumHeight(32)
        self.btn_trash_inv.setEnabled(False)
        self.btn_trash_inv.clicked.connect(self._trash_selected_invoice)
        act_row.addWidget(self.btn_trash_inv)
        act_row.addStretch(1)
        layout.addLayout(act_row)

        self.table = QTableWidget(0, 1)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setStyleSheet("QTableWidget{font-size:13px;}")
        self.table.itemSelectionChanged.connect(self._on_table_sel)
        # Qt shows a sort arrow on col 0 by default; that is not a user choice — ignore until they change sort.
        self._due_header_user_sorted = False
        self._due_sort_programmatic = False
        self.table.horizontalHeader().sortIndicatorChanged.connect(self._on_due_sort_indicator_user)
        layout.addWidget(self.table, 1)

        footer = QLabel("Tip: use Payments → Add Payment (it will auto-allocate FIFO to invoices).")
        footer.setStyleSheet("color:#444;")
        layout.addWidget(footer)

        self._apply_columns()

    def _on_due_sort_indicator_user(self, _logical_index: int, _order: Qt.SortOrder) -> None:
        if self._due_sort_programmatic:
            return
        self._due_header_user_sorted = True

    def _on_table_sel(self) -> None:
        inv_id, path = self._selected_invoice_meta()
        can_xl = self._view == "invoice" and bool(path and str(path).strip())
        self.btn_open_xl.setEnabled(can_xl)
        self.btn_trash_inv.setEnabled(self._view == "invoice" and inv_id is not None)

    def _selected_invoice_meta(self) -> tuple[int | None, str | None]:
        if self._view != "invoice":
            return None, None
        r = self.table.currentRow()
        if r < 0:
            return None, None
        it = self.table.item(r, 1)
        if it is None:
            return None, None
        iid = it.data(Qt.UserRole)
        path = it.data(Qt.UserRole + 1)
        inv_id = int(iid) if iid is not None else None
        p = str(path).strip() if path else None
        return inv_id, p or None

    def _open_selected_invoice_excel(self) -> None:
        _, path = self._selected_invoice_meta()
        if not path:
            QMessageBox.information(self, "Excel", "No file path stored for this invoice.")
            return
        ok, err = open_local_file(path)
        if not ok:
            QMessageBox.warning(self, "Open file", err)

    def _trash_selected_invoice(self) -> None:
        inv_id, path = self._selected_invoice_meta()
        if inv_id is None:
            return
        has_xl = bool(path and str(path).strip())
        choice = confirm_trash_invoice(self, has_excel_path=has_xl)
        if choice == TrashInvoiceChoice.CANCEL:
            return

        if choice == TrashInvoiceChoice.DB_ONLY:
            try:
                with transaction(self._repo.conn):
                    self._repo.soft_delete_invoice(inv_id)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
        else:
            r = self.table.currentRow()
            inv_no = ""
            if r >= 0:
                cell = self.table.item(r, 1)
                if cell is not None:
                    inv_no = cell.text().strip()
            if not confirm_invoice_permanent_delete(self, inv_no):
                return
            try:
                with transaction(self._repo.conn):
                    self._repo.permanently_delete_invoice(inv_id)
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                return
            out = self._repo.get_setting("invoice_output_folder", "")
            ok, err = delete_invoice_excel_if_allowed(str(path or ""), out)
            if path and (not ok) and err:
                QMessageBox.warning(
                    self,
                    "Excel file",
                    "The invoice was removed from the database, but the Excel file could not be deleted:\n"
                    + err,
                )

        self.refresh(today=date.today())
        self.data_changed.emit()

    def _due_range_bounds(self) -> tuple[date, date]:
        """Inclusive due_date bounds (swapped if user picks reverse order)."""
        a = self.due_from_de.date().toPython()
        b = self.due_to_de.date().toPython()
        if a <= b:
            return a, b
        return b, a

    def set_filter(self, due_today: bool = False, overdue: bool = False) -> None:
        """Apply status filter and widen due-date range so counts match dashboard alerts."""
        t = date.today()
        q = QDate(t.year, t.month, t.day)
        if due_today:
            self._filter = "due_today"
            self.filter_cb.setCurrentIndex(1)
            self.due_from_de.setDate(q)
            self.due_to_de.setDate(q)
        elif overdue:
            self._filter = "overdue"
            self.filter_cb.setCurrentIndex(2)
            # Alerts count every overdue invoice; default month range hid older dues.
            self.due_from_de.setDate(QDate(2000, 1, 1))
            self.due_to_de.setDate(q)
        else:
            self._filter = "all"
            self.filter_cb.setCurrentIndex(0)

    def _on_filter_changed(self) -> None:
        self._filter = str(self.filter_cb.currentData())
        self.refresh(today=date.today())

    def _on_view_changed(self) -> None:
        self._view = str(self.view_cb.currentData())
        self._due_header_user_sorted = False
        self._apply_columns()
        self.refresh(today=date.today())

    def _apply_columns(self) -> None:
        if self._view == "customer":
            headers = ["Customer", "Outstanding", "Oldest Due", "Invoices", "Days Overdue", "Status"]
        else:
            headers = ["Customer", "Invoice No", "Invoice Date", "Due Date", "Outstanding", "Days Overdue", "Status"]

        self._due_sort_programmatic = True
        try:
            self.table.clear()
            self.table.setColumnCount(len(headers))
            self.table.setHorizontalHeaderLabels(headers)

            header_view = self.table.horizontalHeader()
            header_view.setStretchLastSection(True)

            if self._view == "customer":
                header_view.setSectionResizeMode(0, QHeaderView.Stretch)
                header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)
                header_view.setSectionResizeMode(2, QHeaderView.ResizeToContents)
                header_view.setSectionResizeMode(3, QHeaderView.ResizeToContents)
                header_view.setSectionResizeMode(4, QHeaderView.ResizeToContents)
                header_view.setSectionResizeMode(5, QHeaderView.ResizeToContents)
            else:
                header_view.setSectionResizeMode(0, QHeaderView.Stretch)  # customer
                header_view.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # invoice no
                header_view.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # inv date
                header_view.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # due date
                header_view.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # outstanding
                header_view.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # days
                header_view.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # status
        finally:
            self._due_sort_programmatic = False

    def refresh(self, today: date) -> None:
        only_due_today = self._filter == "due_today"
        only_overdue = self._filter == "overdue"

        # Status filters (Due today / Overdue) must show every matching invoice, not only
        # those whose due date falls in the month-range picker (used for "All Outstanding").
        if only_due_today or only_overdue:
            df, dt = None, None
        else:
            df, dt = self._due_range_bounds()
        if self._view == "customer":
            rows = self._repo.due_customer_rows(
                today=today,
                only_due_today=only_due_today,
                only_overdue=only_overdue,
                due_from=df,
                due_to=dt,
            )
        else:
            rows = self._repo.due_rows(
                today=today,
                only_due_today=only_due_today,
                only_overdue=only_overdue,
                due_from=df,
                due_to=dt,
            )

        # Preserve sort only after the user changes the header; otherwise Qt's default col-0 arrow misleads us.
        header = self.table.horizontalHeader()
        if self._due_header_user_sorted:
            sort_col = header.sortIndicatorSection()
            sort_order = header.sortIndicatorOrder()
            had_indicator = header.isSortIndicatorShown()
            nc = self.table.columnCount()
            if sort_col < 0 or sort_col >= nc:
                sort_col = -1
                had_indicator = False
        else:
            sort_col = -1
            had_indicator = False
            sort_order = Qt.SortOrder.AscendingOrder

        # Performance: disable sorting & repaints during bulk update.
        self.table.setSortingEnabled(False)
        self.table.setUpdatesEnabled(False)

        self.table.setRowCount(len(rows))
        total_outstanding = 0.0
        for i, r in enumerate(rows):
            if self._view == "customer":
                status = (
                    "Overdue"
                    if r.oldest_due_date < today
                    else ("Due Today" if r.oldest_due_date == today else "Upcoming")
                )
                total_outstanding += float(r.outstanding)

                # For correct column sorting, keep human-readable text in DisplayRole
                # but store numeric/date sort keys in UserRole.
                items = []
                it0 = _SortItem(r.customer_name)
                it0.setData(Qt.UserRole, r.customer_name.lower())
                items.append(it0)

                it1 = _SortItem(f"{r.outstanding:,.2f}")
                it1.setData(Qt.UserRole, float(r.outstanding))
                items.append(it1)

                it2 = _SortItem(r.oldest_due_date.strftime("%d-%m-%Y"))
                it2.setData(Qt.UserRole, r.oldest_due_date.toordinal())
                items.append(it2)

                it3 = _SortItem(str(r.invoice_count))
                it3.setData(Qt.UserRole, int(r.invoice_count))
                items.append(it3)

                it4 = _SortItem(str(r.days_overdue))
                it4.setData(Qt.UserRole, int(r.days_overdue))
                items.append(it4)

                it5 = _SortItem(status)
                # Stable sort: map statuses to ranks
                status_rank = 2 if status == "Overdue" else (1 if status == "Due Today" else 0)
                it5.setData(Qt.UserRole, status_rank)
                items.append(it5)
                align_right = {1, 3, 4}
            else:
                status = "Overdue" if r.due_date < today else ("Due Today" if r.due_date == today else "Upcoming")
                total_outstanding += float(r.outstanding)

                items = []
                it0 = _SortItem(r.customer_name)
                it0.setData(Qt.UserRole, r.customer_name.lower())
                items.append(it0)

                it1 = _SortItem(r.invoice_no)
                it1.setData(Qt.UserRole, r.invoice_id)
                it1.setData(Qt.UserRole + 1, r.excel_path or "")
                inv_key = str(r.invoice_no).strip()
                if inv_key.isdigit():
                    it1.setData(Qt.UserRole + 2, (0, int(inv_key)))
                else:
                    it1.setData(Qt.UserRole + 2, (1, inv_key.lower()))
                items.append(it1)

                it2 = _SortItem(r.invoice_date.strftime("%d-%m-%Y"))
                it2.setData(Qt.UserRole, r.invoice_date.toordinal())
                items.append(it2)

                it3 = _SortItem(r.due_date.strftime("%d-%m-%Y"))
                it3.setData(Qt.UserRole, r.due_date.toordinal())
                items.append(it3)

                it4 = _SortItem(f"{r.outstanding:,.2f}")
                it4.setData(Qt.UserRole, float(r.outstanding))
                items.append(it4)

                it5 = _SortItem(str(r.days_overdue))
                it5.setData(Qt.UserRole, int(r.days_overdue))
                items.append(it5)

                it6 = _SortItem(status)
                status_rank = 2 if status == "Overdue" else (1 if status == "Due Today" else 0)
                it6.setData(Qt.UserRole, status_rank)
                items.append(it6)
                align_right = {4, 5}

            for col, it in enumerate(items):
                if col in align_right:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.table.setItem(i, col, it)

        self.table.setUpdatesEnabled(True)
        self.table.setSortingEnabled(True)
        self._due_sort_programmatic = True
        try:
            if self._view == "invoice":
                if sort_col < 0 or not had_indicator:
                    self.table.sortByColumn(1, Qt.SortOrder.AscendingOrder)
                else:
                    self.table.sortItems(sort_col, sort_order)
            elif sort_col >= 0 and had_indicator:
                self.table.sortItems(sort_col, sort_order)
        finally:
            self._due_sort_programmatic = False

        view_label = "Customer-wise totals" if self._view == "customer" else "Invoice-wise"
        if only_due_today:
            range_note = "  |  Showing all invoices with balance due today (date range ignored)"
        elif only_overdue:
            range_note = "  |  Showing all overdue invoices (date range ignored)"
        elif df is not None and dt is not None:
            range_note = f"  |  Due {df.strftime('%d-%m-%Y')}–{dt.strftime('%d-%m-%Y')} (inclusive)"
        else:
            range_note = ""
        self.summary.setText(
            f"View: {view_label}{range_note}  |  Total outstanding: {total_outstanding:,.2f}  |  Rows: {len(rows)}"
        )
        self._on_table_sel()

