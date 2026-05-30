from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ..app_info import APP_DISPLAY_NAME
from .theme import apply_theme


def build_qt_app(*, dark: bool = False) -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setStyle("Fusion")
    apply_theme(app, dark=dark)

    font = QFont("Segoe UI", 10)
    if not font.exactMatch():
        font = QFont()
        font.setPointSize(10)
    font.setHintingPreference(QFont.HintingPreference.PreferFullHinting)
    app.setFont(font)
    return app
