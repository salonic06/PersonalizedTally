from __future__ import annotations

from datetime import date

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from ..notifications import AppNotification, NavAction, collect_notifications
from ..repo import Repo


class NotificationsDialog(QDialog):
    open_nav = Signal(str)

    def __init__(self, repo: Repo, parent=None) -> None:
        super().__init__(parent)
        self._repo = repo
        self.setWindowTitle("Reminders")
        self.resize(480, 320)

        layout = QVBoxLayout(self)
        self._summary = QLabel()
        self._summary.setWordWrap(True)
        self._summary.setStyleSheet("color:#475569; font-size:13px;")
        layout.addWidget(self._summary)

        self._list = QListWidget()
        self._list.setStyleSheet("QListWidget{font-size:13px;} QListWidget::item{padding:8px;}")
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        self._btn_go = QPushButton("Open list")
        self._btn_go.setMinimumHeight(32)
        self._btn_refresh = QPushButton("Refresh")
        self._btn_refresh.setMinimumHeight(32)
        self._btn_close = QPushButton("Close")
        self._btn_close.setMinimumHeight(32)
        btn_row.addWidget(self._btn_go)
        btn_row.addStretch(1)
        btn_row.addWidget(self._btn_refresh)
        btn_row.addWidget(self._btn_close)
        layout.addLayout(btn_row)

        self._btn_go.clicked.connect(self._on_go)
        self._btn_refresh.clicked.connect(self.reload)
        self._btn_close.clicked.connect(self.accept)
        self._list.itemDoubleClicked.connect(lambda _: self._on_go())

        self._items: list[AppNotification] = []
        self.reload()

    def reload(self) -> None:
        self._items = collect_notifications(self._repo, date.today())
        self._list.clear()
        if not self._items:
            self._summary.setText("Nothing to act on today.")
            self._btn_go.setEnabled(False)
            return

        self._summary.setText(
            f"{date.today().strftime('%d %b %Y')} — {len(self._items)} item"
            f"{'' if len(self._items) == 1 else 's'}"
        )
        self._btn_go.setEnabled(True)
        for n in self._items:
            text = f"{n.title}\n{n.detail}"
            item = QListWidgetItem(text)
            item.setData(256, n.nav_action)
            item.setData(257, n.action_label)
            self._list.addItem(item)
        self._list.setCurrentRow(0)
        self._update_go_label()
        self._list.currentRowChanged.connect(lambda _: self._update_go_label())

    def _update_go_label(self) -> None:
        item = self._list.currentItem()
        if item is None:
            self._btn_go.setText("Open list")
            return
        label = item.data(257) or "Open list"
        self._btn_go.setText(str(label))

    def _on_go(self) -> None:
        item = self._list.currentItem()
        if item is None:
            return
        action: NavAction = item.data(256) or "none"
        if action and action != "none":
            self.open_nav.emit(action)
            self.accept()
