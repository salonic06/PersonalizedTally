from __future__ import annotations

from datetime import date
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QTreeWidgetItem,
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..db.conn import transaction

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
from .nav_brand import make_nav_brand
from .nav_tree import NavTreeWidget
from .theme import (
    SETTING_UI_DARK_MODE,
    apply_nav_tree_palette,
    apply_reminders_button,
    apply_theme,
    apply_theme_from_repo,
    dark_mode_from_setting,
    is_dark_mode_enabled,
    nav_section_color,
)
from .toggle_switch import ToggleSwitch
from .window_geometry import save_main_window_state

Role = Literal["owner", "worker"]

# label, stack index (-1 = section header), roles allowed to see entry
_NAV_DEF: tuple[tuple[str, int, frozenset[str]], ...] = (
    ("Overview", -1, frozenset({"owner", "worker"})),
    ("Dashboard", 0, frozenset({"owner", "worker"})),
    ("Sales", -1, frozenset({"owner", "worker"})),
    ("Invoices", 1, frozenset({"owner", "worker"})),
    ("Due / Outstanding", 2, frozenset({"owner", "worker"})),
    ("Receivables aging", 3, frozenset({"owner", "worker"})),
    ("Customer Ledger", 4, frozenset({"owner", "worker"})),
    ("Payments", 7, frozenset({"owner", "worker"})),
    ("Stock", -1, frozenset({"owner", "worker"})),
    ("Raw materials & stock", 5, frozenset({"owner", "worker"})),
    ("Production", 6, frozenset({"owner", "worker"})),
    ("Administration", -1, frozenset({"owner"})),
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
        top.setObjectName("headerBar")
        top_layout = QHBoxLayout(top)
        top_layout.setContentsMargins(12, 10, 12, 10)

        self.search = QLineEdit()
        self.search.setObjectName("searchInput")
        self.search.setPlaceholderText("Search customers, invoices, payments, products… (Enter)")
        self.search.setMinimumHeight(34)
        self.search.returnPressed.connect(self._run_global_search)
        top_layout.addWidget(self.search, 1)

        dark_lay = QHBoxLayout()
        dark_lay.setSpacing(8)
        dark_lbl = QLabel("Dark")
        dark_lbl.setObjectName("mutedHint")
        self.toggle_dark = ToggleSwitch()
        self.toggle_dark.setToolTip("Switch between light and dark theme")
        self.toggle_dark.toggled.connect(self._on_dark_mode_toggled)
        dark_lay.addWidget(dark_lbl)
        dark_lay.addWidget(self.toggle_dark)
        top_layout.addLayout(dark_lay)

        self.btn_alerts = QPushButton("Reminders")
        self.btn_due_today = QPushButton("Due Today")
        self.btn_overdue = QPushButton("Overdue")
        self.btn_add_payment = QPushButton("Add Payment")
        for b in (self.btn_alerts, self.btn_due_today, self.btn_overdue, self.btn_add_payment):
            b.setMinimumHeight(34)
        apply_reminders_button(self.btn_alerts)
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

        nav_panel = QWidget()
        nav_panel.setObjectName("navPanel")
        nav_panel.setFixedWidth(252)
        nav_lay = QVBoxLayout(nav_panel)
        nav_lay.setContentsMargins(8, 8, 8, 8)
        nav_lay.addWidget(make_nav_brand(APP_DISPLAY_NAME))
        self.nav = NavTreeWidget()
        self.nav.setObjectName("appNav")
        self.nav.setHeaderHidden(True)
        nav_lay.addWidget(self.nav, 1)
        self._nav_panel = nav_panel

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

        self._last_nav_page: QTreeWidgetItem | None = None
        self._populate_nav()
        self._sync_dark_mode_checkbox()

        main_layout.addWidget(self.btn_toggle_nav, 0, Qt.AlignmentFlag.AlignTop)
        main_layout.addWidget(nav_panel)
        main_layout.addWidget(self.stack, 1)
        root_layout.addWidget(main, 1)

        self.nav.itemSelectionChanged.connect(self._on_nav_changed)
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

        app = QApplication.instance()
        if app is not None:
            apply_theme_from_repo(app, self._repo)
        self._apply_nav_tree_theme()

    def _populate_nav(self) -> None:
        self.nav.clear()
        section = None
        first_page = None
        section_font = QFont()
        section_font.setPixelSize(12)
        section_font.setWeight(QFont.Weight.Bold)
        section_brush = QBrush(nav_section_color(self._repo))

        for label, stack_idx, roles in _NAV_DEF:
            if self._role not in roles:
                continue
            if stack_idx < 0:
                section = NavTreeWidget.make_section(label)
                section.setFont(0, section_font)
                section.setForeground(0, section_brush)
                self.nav.addTopLevelItem(section)
                continue
            page = NavTreeWidget.make_page(label, stack_idx)
            if section is not None:
                section.addChild(page)
            else:
                self.nav.addTopLevelItem(page)
            if first_page is None:
                first_page = page

        if first_page is not None:
            self.nav.setCurrentItem(first_page)
            self._last_nav_page = first_page
        self.nav.expand_all_sections()

    def _iter_nav_pages(self):
        for i in range(self.nav.topLevelItemCount()):
            top = self.nav.topLevelItem(i)
            if top is None:
                continue
            if top.childCount() > 0:
                for j in range(top.childCount()):
                    child = top.child(j)
                    if child is not None:
                        yield child
            elif top.data(0, Qt.ItemDataRole.UserRole) is not None:
                yield top

    def _apply_nav_tree_theme(self) -> None:
        apply_nav_tree_palette(self.nav, dark=is_dark_mode_enabled(self._repo))

    def _sync_dark_mode_checkbox(self) -> None:
        self.toggle_dark.blockSignals(True)
        self.toggle_dark.setChecked(
            dark_mode_from_setting(self._repo.get_setting(SETTING_UI_DARK_MODE, "0"))
        )
        self.toggle_dark.blockSignals(False)

    def _on_dark_mode_toggled(self, dark: bool) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_theme(app, dark=dark)
        with transaction(self._repo.conn):
            self._repo.set_setting(SETTING_UI_DARK_MODE, "1" if dark else "0")
        self._apply_nav_tree_theme()
        self._refresh_nav_section_colors()
        self.page_home.refresh()
        idx = self.stack.currentIndex()
        self._refresh_stack_page(idx)

    def _refresh_nav_section_colors(self) -> None:
        color = QBrush(nav_section_color(self._repo))
        for i in range(self.nav.topLevelItemCount()):
            top = self.nav.topLevelItem(i)
            if top is not None and NavTreeWidget.is_section(top):
                top.setForeground(0, color)
        self.nav.expand_all_sections()

    def _set_nav_stack(self, stack_idx: int, *, quiet: bool = False) -> bool:
        target: QTreeWidgetItem | None = None
        for item in self._iter_nav_pages():
            if item.data(0, Qt.ItemDataRole.UserRole) == stack_idx:
                target = item
                break
        if target is None:
            if not quiet:
                QMessageBox.information(
                    self,
                    "Restricted",
                    "That screen is only available when signed in as owner.",
                )
            return False
        parent = target.parent()
        if parent is not None:
            parent.setExpanded(True)
        self.nav.blockSignals(True)
        self.nav.setCurrentItem(target)
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
            self._sync_dark_mode_checkbox()

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
        self._nav_panel.setVisible(not self._nav_panel.isVisible())

    def _on_fg_help_navigate(self, where: str) -> None:
        if where == "seed_data":
            self._set_nav_stack(11)
        elif where == "batch_costing":
            self._set_nav_stack(6)
            self.page_batches.refresh_all()
            self.page_batches.open_batch_costing_tab()

    def _on_nav_changed(self) -> None:
        item = self.nav.currentItem()
        if NavTreeWidget.is_section(item):
            if self._last_nav_page is not None:
                self.nav.blockSignals(True)
                self.nav.setCurrentItem(self._last_nav_page)
                self.nav.blockSignals(False)
            return
        if not NavTreeWidget.is_page(item):
            return
        self._last_nav_page = item
        stack_idx = item.data(0, Qt.ItemDataRole.UserRole)
        idx = int(stack_idx)
        if self.stack.currentIndex() == idx:
            return
        self.stack.setCurrentIndex(idx)
        self._refresh_stack_page(idx)

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
