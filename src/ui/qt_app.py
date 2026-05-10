from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ..app_info import APP_DISPLAY_NAME
from .theme import global_stylesheet


def build_qt_app() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setStyle("Fusion")
    app.setStyleSheet(global_stylesheet())

    font = QFont()
    font.setPointSize(10)
    app.setFont(font)
    return app

