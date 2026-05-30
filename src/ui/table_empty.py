"""Centered empty-state row for data tables."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem

from .theme import is_dark_mode_enabled


def clear_table_body_for_fill(table: QTableWidget) -> None:
    """Remove empty-state widgets before loading data rows."""
    table.clearSpans()
    rows = table.rowCount()
    cols = table.columnCount()
    for r in range(rows):
        for c in range(cols):
            if table.cellWidget(r, c) is not None:
                table.removeCellWidget(r, c)
    table.setRowCount(0)


def set_table_empty_state(table: QTableWidget, message: str, *, repo=None) -> None:
    """Replace table body with a single non-selectable message row."""
    cols = max(1, table.columnCount())
    clear_table_body_for_fill(table)
    table.setRowCount(1)
    table.setSpan(0, 0, 1, cols)
    table.setRowHeight(0, 56)
    item = QTableWidgetItem(message)
    item.setFlags(Qt.ItemFlag.NoItemFlags)
    item.setTextAlignment(
        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
    )
    muted = "#94a3b8" if repo is not None and is_dark_mode_enabled(repo) else "#64748b"
    item.setForeground(QBrush(QColor(muted)))
    font = QFont(item.font())
    font.setItalic(True)
    item.setFont(font)
    table.setItem(0, 0, item)
    for c in range(1, cols):
        table.setItem(0, c, QTableWidgetItem(""))
    table.clearSelection()
