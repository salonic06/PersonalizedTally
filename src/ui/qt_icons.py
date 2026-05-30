from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QStyle


def trash_row_icon() -> QIcon:
    """Bundled minimal line-art trash icon (`assets/trash_row.png`), with Qt fallback."""
    try:
        from ..paths import get_paths

        p = get_paths().root / "assets" / "trash_row.png"
        if p.is_file():
            return QIcon(str(p))
    except Exception:
        pass
    style = QApplication.style()
    if style is not None:
        return style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon)
    return QIcon()


def trash_icon_button_size() -> QSize:
    return QSize(20, 20)
