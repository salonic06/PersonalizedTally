from __future__ import annotations

from datetime import date
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..app_info import APP_DISPLAY_NAME
from ..db.conn import connect
from ..db.migrate import migrate
from ..open_file import open_local_file
from ..paths import get_paths
from ..notifications import collect_notifications
from ..repo import Repo, SearchHit
from .change_password_dialog import ChangePasswordDialog
from .notifications_dialog import NotificationsDialog
from .pages.aging_page import AgingPage
from .pages.analytics_page import AnalyticsPage
from .pages.audit_log_page import AuditLogPage
from .pages.batches_page import BatchesPage
from .pages.due_page import DuePage
from .pages.home_page import HomePage
from .pages.invoice_page import InvoicePage
from .pages.ledger_page import LedgerPage
from .pages.payments_page import PaymentsPage
from .pages.raw_materials_page import RawMaterialsPage
from .pages.seed_page import SeedPage
from .pages.settings_page import SettingsPage
from .pages.trash_page import TrashPage
from .search_dialog import SearchResultsDialog
from .window_geometry import save_main_window_state

Role = Literal["owner", "worker"]

# label, stack index, roles allowed to see nav entry
_NAV_DEF: tuple[tuple[str, int, frozenset[str]], ...] = (
    ("Dashboard", 0, frozenset({"owner", "worker"})),
    ("Invoices", 1, frozenset({"owner", "worker"})),
    ("Due / Outstanding", 2, frozenset({"owner", "worker"})),
    ("Receivables aging", 3, frozenset({"owner", "worker"})),
    ("Customer Ledger", 4, frozenset({"owner", "worker"})),
    ("Raw materials & stock", 5, frozenset({"owner", "worker"})),
    ("Production", 6, frozenset({"owner", "worker"})),
    ("Payments", 7, frozenset({"owner", "worker"})),
    ("Analytics", 8, frozenset({"owner"})),
    ("Audit log", 9, frozenset({"owner"})),
    ("Trash", 10, frozenset({"owner"})),
    ("Setup (Seed Data)", 11, frozenset({"owner"})),
    ("Settings", 12, frozenset({"owner"})),
)


class MainWindow(QMainWindow):
    #: When ``Sign out`` runs, set True so ``app.main`` can show the login dialog again.
    wants_relogin = False

    def __init__(
        self,
        repo: Repo | None = None,
        *,
        role: Role = "owner",
        username: str = "",
    ) -> None:
        super().__init__()
        self._role = role
        self._username = (username or "").strip()
        title = APP_DISPLAY_NAME
        if self._username:
            title = f"{APP_DISPLAY_NAME} — {self._username} ({role})"
        self.setWindowTitle(title)
        self.resize(1100, 700)

        if repo is None:
            self._paths = get_paths()
            self._conn = connect(self._paths.db_path)
            migrate(self._conn)
            self._repo = Repo(self._conn)
            self._owns_conn = True
        else:
            self._repo = repo
            self._conn = repo.conn
            self._owns_conn = False

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)

        top = QWidget()
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(0, 0, 0, 0)

        top_layout.addWidget(QLabel("Search"))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Customer, invoice, payment, product, RM, lot / supplier ref / notes… (Enter)")
        self.search.setMinimumHeight(34)
        self.search.returnPressed.connect(self._run_global_search)
        top_layout.addWidget(self.search, 1)

        self.btn_alerts = QPushButton("Reminders")
        self.btn_due_today = QPushButton("Due Today")
        self.btn_overdue = QPushButton("Overdue")
        self.btn_add_payment = QPushButton("Add Payment")
        for b in (self.btn_alerts, self.btn_due_today, self.btn_overdue, self.btn_add_payment):
            b.setMinimumHeight(34)
        top_layout.addWidget(self.btn_alerts)
        top_layout.addWidget(self.btn_due_today)
        top_layout.addWidget(self.btn_overdue)
        top_layout.addWidget(self.btn_add_payment)

        top_layout.addSpacing(12)
        self.btn_change_pw = QPushButton("Password…")
        self.btn_change_pw.setMinimumHeight(34)
        self.btn_change_pw.setToolTip("Change your sign-in password")
        self.btn_sign_out = QPushButton("Sign out")
        self.btn_sign_out.setMinimumHeight(34)
        self.btn_sign_out.setToolTip("Return to the login screen")
        top_layout.addWidget(self.btn_change_pw)
        top_layout.addWidget(self.btn_sign_out)

        root_layout.addWidget(top)

        main = QWidget()
        main_layout = QHBoxLayout(main)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_toggle_nav = QPushButton("☰")
        self.btn_toggle_nav.setFixedWidth(36)
        self.btn_toggle_nav.setMinimumHeight(34)

        self.nav = QListWidget()
        self.nav.setFixedWidth(220)
        self.nav.setSpacing(6)
        self.nav.setStyleSheet("QListWidget{font-size:14px;} QListWidget::item{padding:10px;} ")

        self.stack = QStackedWidget()

        self.page_home = HomePage(repo=self._repo)
        self.page_invoices = InvoicePage(repo=self._repo)
        self.page_due = DuePage(repo=self._repo)
        self.page_aging = AgingPage(repo=self._repo)
        self.page_ledger = LedgerPage(repo=self._repo)
        self.page_raw_materials = RawMaterialsPage(repo=self._repo)
        self.page_batches = BatchesPage(repo=self._repo)
        self.page_payments = PaymentsPage(repo=self._repo)
        self.page_analytics = AnalyticsPage(repo=self._repo)
        self.page_audit = AuditLogPage(repo=self._repo)
        self.page_trash = TrashPage(repo=self._repo)
        self.page_seed = SeedPage(repo=self._repo)
        self.page_settings = SettingsPage(repo=self._repo)

        self.stack.addWidget(self.page_home)  # 0
        self.stack.addWidget(self.page_invoices)  # 1
        self.stack.addWidget(self.page_due)  # 2
        self.stack.addWidget(self.page_aging)  # 3
        self.stack.addWidget(self.page_ledger)  # 4
        self.stack.addWidget(self.page_raw_materials)  # 5
        self.stack.addWidget(self.page_batches)  # 6
        self.stack.addWidget(self.page_payments)  # 7
        self.stack.addWidget(self.page_analytics)  # 8
        self.stack.addWidget(self.page_audit)  # 9
        self.stack.addWidget(self.page_trash)  # 10
        self.stack.addWidget(self.page_seed)  # 11
        self.stack.addWidget(self.page_settings)  # 12

        self._nav_stack_indices: list[int] = []
        self._populate_nav()

        main_layout.addWidget(self.btn_toggle_nav, 0, Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(self.nav)
        main_layout.addWidget(self.stack, 1)
        root_layout.addWidget(main, 1)

        self.nav.currentRowChanged.connect(self._on_nav_changed)
        self.btn_alerts.clicked.connect(self._open_notifications)
        self.btn_due_today.clicked.connect(lambda: self._open_due(due_today=True))
        self.btn_overdue.clicked.connect(lambda: self._open_due(overdue=True))
        self.btn_add_payment.clicked.connect(self._open_add_payment)
        self.btn_toggle_nav.clicked.connect(self._toggle_nav)
        self.btn_change_pw.clicked.connect(self._change_password)
        self.btn_sign_out.clicked.connect(self._sign_out)

        self.page_payments.data_changed.connect(self._refresh_due_if_visible)
        self.page_seed.data_changed.connect(self._refresh_everything)
        self.page_settings.saved.connect(self._refresh_everything)
        self.page_invoices.created.connect(self._refresh_everything)
        self.page_due.data_changed.connect(self._refresh_everything)
        self.page_ledger.data_changed.connect(self._refresh_everything)
        self.page_trash.data_changed.connect(self._refresh_everything)
        self.page_raw_materials.data_changed.connect(self._refresh_everything)
        self.page_batches.data_changed.connect(self._refresh_everything)
        self.page_batches.fg_help_navigate.connect(self._on_fg_help_navigate)

        self.page_due.refresh(today=date.today())
        self.page_home.refresh()
        self._refresh_alerts_badge()

    def _populate_nav(self) -> None:
        self.nav.clear()
        self._nav_stack_indices = []
        for label, stack_idx, roles in _NAV_DEF:
            if self._role in roles:
                QListWidgetItem(label, self.nav)
                self._nav_stack_indices.append(stack_idx)
        self.nav.setCurrentRow(0)

    def _set_nav_stack(self, stack_idx: int, *, quiet: bool = False) -> bool:
        try:
            nav_row = self._nav_stack_indices.index(stack_idx)
        except ValueError:
            if not quiet:
                QMessageBox.information(
                    self,
                    "Restricted",
                    "That screen is only available when signed in as owner.",
                )
            return False
        self.nav.blockSignals(True)
        self.nav.setCurrentRow(nav_row)
        self.nav.blockSignals(False)
        self.stack.setCurrentIndex(stack_idx)
        self._refresh_stack_page(stack_idx)
        return True

    def _refresh_stack_page(self, stack_idx: int) -> None:
        if stack_idx == 0:
            self.page_home.refresh()
        elif stack_idx == 1:
            self.page_invoices.reload_customers()
        elif stack_idx == 2:
            self.page_due.refresh(today=date.today())
        elif stack_idx == 3:
            self.page_aging.refresh(today=date.today())
        elif stack_idx == 4:
            self.page_ledger.reload_customers()
            self.page_ledger.refresh()
        elif stack_idx == 5:
            self.page_raw_materials.refresh_all()
        elif stack_idx == 6:
            self.page_batches.refresh_all()
        elif stack_idx == 7:
            self.page_payments.reload_customers()
            self.page_payments.reload_recent_payments()
        elif stack_idx == 8:
            self.page_analytics.refresh()
        elif stack_idx == 9:
            self.page_audit.refresh()
        elif stack_idx == 10:
            self.page_trash.refresh()
        elif stack_idx == 11:
            self.page_seed.reload_customers()
            self.page_seed.reload_rm_pick()
        elif stack_idx == 12:
            self.page_settings.load()

    def _change_password(self) -> None:
        if not self._username:
            QMessageBox.information(self, "Password", "No username in session.")
            return
        dlg = ChangePasswordDialog(self._repo, self._username, self)
        dlg.exec()

    def _sign_out(self) -> None:
        r = QMessageBox.question(
            self,
            "Sign out",
            "Sign out and return to the login screen?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        MainWindow.wants_relogin = True
        self.close()

    def _toggle_nav(self) -> None:
        self.nav.setVisible(not self.nav.isVisible())

    def _on_fg_help_navigate(self, where: str) -> None:
        if where == "seed_data":
            self._set_nav_stack(11)
        elif where == "batch_costing":
            self._set_nav_stack(6)
            self.page_batches.refresh_all()
            self.page_batches.open_batch_costing_tab()

    def _on_nav_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._nav_stack_indices):
            return
        stack_idx = self._nav_stack_indices[row]
        self.stack.setCurrentIndex(stack_idx)
        self._refresh_stack_page(stack_idx)

    def _refresh_due_if_visible(self) -> None:
        if self.stack.currentIndex() == 2:
            self.page_due.refresh(today=date.today())

    def _refresh_everything(self) -> None:
        self.page_home.refresh()
        self.page_analytics.refresh()
        self.page_payments.reload_customers()
        self.page_payments.reload_recent_payments()
        self.page_invoices.reload_customers()
        self.page_invoices.reload_items()
        self.page_ledger.reload_customers()
        idx = self.stack.currentIndex()
        if idx == 2:
            self.page_due.refresh(today=date.today())
        elif idx == 3:
            self.page_aging.refresh(today=date.today())
        elif idx == 4:
            self.page_ledger.refresh()
        elif idx == 5:
            self.page_raw_materials.refresh_all()
        elif idx == 6:
            self.page_batches.refresh_all()
        elif idx == 8:
            self.page_analytics.refresh()
        elif idx == 9:
            self.page_audit.refresh()
        elif idx == 10:
            self.page_trash.refresh()
        self._refresh_alerts_badge()

    def _refresh_alerts_badge(self) -> None:
        n = len(collect_notifications(self._repo, date.today()))
        if n > 0:
            self.btn_alerts.setText(f"Reminders ({n})")
            self.btn_alerts.setToolTip(
                f"{n} reminder(s): stock below reorder, invoices due today, or overdue balances."
            )
        else:
            self.btn_alerts.setText("Reminders")
            self.btn_alerts.setToolTip(
                "Stock below reorder level, invoices due today, and overdue customer balances."
            )

    def _open_notifications(self) -> None:
        dlg = NotificationsDialog(self._repo, self)
        dlg.open_nav.connect(self._on_notification_nav)
        dlg.exec()
        self._refresh_alerts_badge()
        self.page_home.refresh_alerts()

    def _on_notification_nav(self, action: str) -> None:
        if action == "open_due_today":
            self._open_due(due_today=True)
        elif action == "open_overdue":
            self._open_due(overdue=True)
        elif action == "open_raw_materials":
            self._set_nav_stack(5)
            self.page_raw_materials.refresh_all()

    def _open_due(self, due_today: bool = False, overdue: bool = False) -> None:
        self._set_nav_stack(2)
        self.page_due.set_filter(due_today=due_today, overdue=overdue)
        self.page_due.refresh(today=date.today())

    def _open_add_payment(self) -> None:
        self._set_nav_stack(7)
        self.page_payments.focus_new_payment()

    def _run_global_search(self) -> None:
        q = self.search.text().strip()
        if len(q) < 2:
            QMessageBox.information(self, "Search", "Type at least 2 characters, then press Enter.")
            return
        hits = self._repo.search_hits(q)
        if not hits:
            QMessageBox.information(self, "Search", "No matches.")
            return
        dlg = SearchResultsDialog(hits, self)
        dlg.exec()
        h = dlg.selected_hit()
        if h is None or dlg.action == "cancel":
            return
        if dlg.action == "open_excel":
            path = h.excel_path or ""
            if not path.strip():
                QMessageBox.information(self, "Excel", "No file path stored for this invoice.")
            else:
                ok, err = open_local_file(path)
                if not ok:
                    QMessageBox.warning(self, "Open file", err)
            return
        self._navigate_search_hit(h)

    def _navigate_search_hit(self, h: SearchHit) -> None:
        if h.kind == "customer" and h.customer_id is not None:
            self._set_nav_stack(4)
            self.page_ledger.set_customer_id(h.customer_id)
        elif h.kind == "invoice":
            if h.customer_id is not None:
                self._set_nav_stack(4)
                self.page_ledger.set_customer_id(h.customer_id)
            self._set_nav_stack(2)
            self.page_due.refresh(today=date.today())
        elif h.kind == "payment":
            self._set_nav_stack(7)
            self.page_payments.reload_recent_payments()
        elif h.kind == "item":
            if not self._set_nav_stack(11):
                self._set_nav_stack(1)
        elif h.kind in ("raw_material", "rm_lot"):
            self._set_nav_stack(5)
            rid = h.raw_material_id
            if rid is not None:
                self.page_raw_materials.focus_raw_material(int(rid))
            else:
                self.page_raw_materials.refresh_all()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            save_main_window_state(self)
            if self._owns_conn:
                self._conn.close()
        finally:
            super().closeEvent(event)
