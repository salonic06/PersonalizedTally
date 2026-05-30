"""Sidebar navigation — sections always expanded; pages listed underneath."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

_SECTION_KIND = Qt.ItemDataRole.UserRole + 1
_SECTION_NAME = Qt.ItemDataRole.UserRole + 2


class NavTreeWidget(QTreeWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setRootIsDecorated(False)
        self.setIndentation(12)
        self.setAnimated(False)
        self.setExpandsOnDoubleClick(False)
        self.setUniformRowHeights(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAllColumnsShowFocus(False)
        self.itemCollapsed.connect(self._keep_sections_open)

    @classmethod
    def make_section(cls, name: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([name])
        item.setData(0, _SECTION_KIND, "section")
        item.setData(0, _SECTION_NAME, name)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        item.setExpanded(True)
        return item

    @staticmethod
    def make_page(label: str, stack_idx: int) -> QTreeWidgetItem:
        item = QTreeWidgetItem([label])
        item.setData(0, Qt.ItemDataRole.UserRole, stack_idx)
        item.setData(0, _SECTION_KIND, "page")
        return item

    @staticmethod
    def is_section(item: QTreeWidgetItem | None) -> bool:
        return item is not None and item.data(0, _SECTION_KIND) == "section"

    @staticmethod
    def is_page(item: QTreeWidgetItem | None) -> bool:
        return item is not None and item.data(0, _SECTION_KIND) == "page"

    def expand_all_sections(self) -> None:
        for i in range(self.topLevelItemCount()):
            top = self.topLevelItem(i)
            if top is not None and self.is_section(top):
                top.setExpanded(True)

    def _keep_sections_open(self, item: QTreeWidgetItem) -> None:
        if self.is_section(item):
            item.setExpanded(True)
