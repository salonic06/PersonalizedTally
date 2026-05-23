"""Lightweight Fusion styling — readable defaults without extra dependencies."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton

# Calm blue-gray accent; tuned for long accounting sessions.
_ACCENT = "#2563eb"
_ACCENT_HOVER = "#1d4ed8"
_ACCENT_SOFT = "#eff6ff"
_SURFACE = "#f8fafc"
_BORDER = "#e2e8f0"
_TEXT = "#0f172a"
_MUTED = "#64748b"


def global_stylesheet() -> str:
    return f"""
    QWidget {{
        background: {_SURFACE};
        color: {_TEXT};
        font-size: 13px;
    }}
    QMainWindow {{
        background: {_SURFACE};
    }}
    QLabel {{
        color: {_TEXT};
    }}
    QLabel#pageTitle {{
        font-size: 22px;
        font-weight: 700;
        color: {_TEXT};
    }}
    QLabel#pageSubtitle {{
        font-size: 13px;
        color: {_MUTED};
        margin-bottom: 2px;
    }}
    QLineEdit, QTextEdit, QComboBox {{
        background: #ffffff;
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 4px 8px;
        selection-background-color: {_ACCENT};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QPushButton {{
        background: #ffffff;
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 6px 14px;
        min-height: 28px;
    }}
    QPushButton:hover {{
        border-color: #cbd5e1;
        background: #f1f5f9;
    }}
    QPushButton:pressed {{
        background: #e2e8f0;
    }}
    QPushButton#btnPrimary {{
        background: {_ACCENT};
        color: #ffffff;
        border: none;
        font-weight: 600;
        padding: 8px 18px;
        min-height: 32px;
    }}
    QPushButton#btnPrimary:hover {{
        background: {_ACCENT_HOVER};
    }}
    QPushButton#btnPrimary:pressed {{
        background: #1e40af;
    }}
    QPushButton#btnPrimary:disabled {{
        background: #94a3b8;
        color: #e2e8f0;
    }}
    QPushButton#btnAccent {{
        background: {_ACCENT_SOFT};
        color: #1e40af;
        border: 1px solid #93c5fd;
        font-weight: 600;
    }}
    QPushButton#btnAccent:hover {{
        background: #dbeafe;
        border-color: #60a5fa;
    }}
    QListWidget#appNav {{
        background: #ffffff;
        border: 1px solid {_BORDER};
        border-radius: 10px;
        padding: 8px 6px;
        font-size: 15px;
    }}
    QListWidget#appNav::item {{
        padding: 11px 10px;
        border-radius: 8px;
        margin: 2px 0;
    }}
    QListWidget#appNav::item:selected {{
        background: {_ACCENT};
        color: #ffffff;
    }}
    QListWidget#appNav::item:hover:!selected {{
        background: #f1f5f9;
    }}
    QListWidget {{
        background: #ffffff;
        border: 1px solid {_BORDER};
        border-radius: 8px;
        padding: 6px;
    }}
    QListWidget::item:selected {{
        background: {_ACCENT};
        color: #ffffff;
    }}
    QTableWidget {{
        background: #ffffff;
        border: 1px solid {_BORDER};
        border-radius: 8px;
        gridline-color: {_BORDER};
    }}
    QHeaderView::section {{
        background: #f1f5f9;
        padding: 6px;
        border: none;
        border-bottom: 1px solid {_BORDER};
        font-weight: 600;
    }}
    QScrollArea {{
        border: none;
    }}
    QGroupBox {{
        font-weight: 600;
        border: 1px solid {_BORDER};
        border-radius: 8px;
        margin-top: 12px;
        padding-top: 8px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
    }}
    QFrame#dashCard {{
        background: #ffffff;
        border: 1px solid {_BORDER};
        border-radius: 10px;
        padding: 12px 14px;
    }}
    QFrame#formCard {{
        background: #ffffff;
        border: 1px solid {_BORDER};
        border-radius: 10px;
        padding: 14px 16px;
    }}
    """


def apply_primary_button(button: QPushButton) -> None:
    button.setObjectName("btnPrimary")


def apply_accent_button(button: QPushButton) -> None:
    button.setObjectName("btnAccent")
