"""Persist main-window position/size and maximized flag via ``QSettings``."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QMainWindow

from ..app_info import APP_DISPLAY_NAME

_SETTINGS_ORG = "PersonalizedTallyDesktop"


def _settings() -> QSettings:
    return QSettings(_SETTINGS_ORG, APP_DISPLAY_NAME)


def apply_main_window_state(win: QMainWindow) -> None:
    """Restore geometry; default first-run behaviour is maximized."""
    s = _settings()
    geo = s.value("main_window/geometry")
    if geo is not None:
        win.restoreGeometry(geo)
    else:
        win.resize(1100, 700)

    maximized = s.value("main_window/maximized", True)
    if isinstance(maximized, str):
        maximized = maximized.lower() in ("true", "1", "yes")

    if bool(maximized):
        win.showMaximized()
    else:
        win.showNormal()


def save_main_window_state(win: QMainWindow) -> None:
    s = _settings()
    s.setValue("main_window/maximized", win.isMaximized())
    s.setValue("main_window/geometry", win.saveGeometry())
