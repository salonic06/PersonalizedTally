from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from ..repo import SearchHit


class SearchResultsDialog(QDialog):
    """Pick a search hit; optional Open Excel for invoices."""

    def __init__(self, hits: list[SearchHit], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Search results")
        self.resize(560, 420)
        self._selected: SearchHit | None = None
        self.action: str = "cancel"  # cancel | go | open_excel

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"{len(hits)} match(es). Double-click or use buttons below."))

        self.list_w = QListWidget()
        self.list_w.setAlternatingRowColors(True)
        for h in hits:
            text = f"[{h.kind}] {h.title}"
            if h.detail:
                text += f"  —  {h.detail}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, h)
            self.list_w.addItem(item)
        self.list_w.itemDoubleClicked.connect(self._on_double)
        layout.addWidget(self.list_w, 1)

        row = QHBoxLayout()
        self.btn_open = QPushButton("Open invoice Excel")
        self.btn_open.setEnabled(False)
        self.btn_go = QPushButton("Go to…")
        self.btn_go.setEnabled(False)
        row.addWidget(self.btn_open)
        row.addWidget(self.btn_go)
        row.addStretch(1)
        layout.addLayout(row)

        self.list_w.currentItemChanged.connect(self._on_sel_change)
        self.btn_open.clicked.connect(self._open_excel)
        self.btn_go.clicked.connect(self._accept_go)

        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def _current_hit(self) -> SearchHit | None:
        it = self.list_w.currentItem()
        if it is None:
            return None
        return it.data(Qt.UserRole)

    def _on_sel_change(self) -> None:
        h = self._current_hit()
        self.btn_go.setEnabled(h is not None)
        self.btn_open.setEnabled(
            h is not None and h.kind == "invoice" and bool(h.excel_path and str(h.excel_path).strip())
        )

    def _on_double(self) -> None:
        self._accept_go()

    def _open_excel(self) -> None:
        h = self._current_hit()
        if h is None or not h.excel_path:
            return
        self._selected = h
        self.action = "open_excel"
        self.accept()

    def _accept_go(self) -> None:
        h = self._current_hit()
        if h is None:
            return
        self._selected = h
        self.action = "go"
        self.accept()

    def selected_hit(self) -> SearchHit | None:
        return self._selected
