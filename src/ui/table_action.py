"""Centered table action cells — flat icons, no nested button chrome."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QHeaderView, QPushButton, QTableWidget, QWidget

from .qt_icons import trash_icon_button_size, trash_row_icon


def polish_data_table(table: QTableWidget, *, row_height: int = 40) -> None:
    vh = table.verticalHeader()
    vh.setVisible(False)
    vh.setDefaultSectionSize(row_height)
    vh.setSectionResizeMode(vh.ResizeMode.Fixed)


def configure_action_column(table: QTableWidget, col: int, *, width: int = 48) -> None:
    table.setColumnWidth(col, width)
    hdr = table.horizontalHeader()
    hdr.setSectionResizeMode(col, QHeaderView.ResizeMode.Fixed)


def make_trash_cell(
    on_click: Callable[[], None],
    *,
    tooltip: str = "Move to trash",
    enabled: bool = True,
) -> QWidget:
    btn = QPushButton()
    btn.setObjectName("btnIconDanger")
    btn.setIcon(trash_row_icon())
    btn.setIconSize(trash_icon_button_size())
    btn.setToolTip(tooltip)
    btn.setEnabled(enabled)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(on_click)

    wrap = QWidget()
    wrap.setObjectName("tableActionCell")
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(0)
    lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)
    return wrap


def make_restore_cell(on_click: Callable[[], None]) -> QWidget:
    return make_text_action_cell("Restore", on_click)


def make_text_action_cell(
    text: str,
    on_click: Callable[[], None],
    *,
    enabled: bool = True,
) -> QWidget:
    btn = QPushButton(text)
    btn.setObjectName("btnTableAction")
    btn.setEnabled(enabled)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    btn.clicked.connect(on_click)

    wrap = QWidget()
    wrap.setObjectName("tableActionCell")
    lay = QHBoxLayout(wrap)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(btn, 0, Qt.AlignmentFlag.AlignCenter)
    return wrap
