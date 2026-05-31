"""Fusion styling — light and dark palettes with shared component tokens."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QPushButton, QTreeWidget

SETTING_UI_DARK_MODE = "ui_dark_mode"

# Muted indigo-violet (Stripe / Linear style — professional, not neon)
_ACCENT = "#5b5bd6"
_ACCENT_HOVER = "#4a4ac0"
_ACCENT_SUBTLE_LIGHT = "#eef0fc"
_ACCENT_SUBTLE_DARK = "#232446"
_ACCENT_ON_LIGHT = "#4343b0"
_ACCENT_ON_DARK = "#c7caff"

# Muted rose (alerts / reminders — not neon red)
_ROSE_LIGHT_BG = "#fff1f2"
_ROSE_LIGHT_TEXT = "#9f1239"
_ROSE_LIGHT_BORDER = "#fecdd3"
_ROSE_DARK_BG = "#4c0519"
_ROSE_DARK_TEXT = "#fecdd3"
_ROSE_DARK_BORDER = "#9f1239"


def dark_mode_from_setting(value: str | None) -> bool:
    return (value or "").strip() in ("1", "true", "yes", "on")


def is_dark_mode_enabled(repo) -> bool:
    return dark_mode_from_setting(repo.get_setting(SETTING_UI_DARK_MODE, "0"))


def global_stylesheet() -> str:
    return stylesheet(dark=False)


def stylesheet(*, dark: bool) -> str:
    return _dark_stylesheet() if dark else _light_stylesheet()


def apply_theme(app: QApplication, *, dark: bool) -> None:
    app.setStyleSheet(stylesheet(dark=dark))


def apply_theme_from_repo(app: QApplication, repo) -> None:
    apply_theme(app, dark=is_dark_mode_enabled(repo))


def nav_section_color(repo) -> QColor:
    if is_dark_mode_enabled(repo):
        return QColor(_ACCENT_ON_DARK)
    return QColor(_ACCENT_ON_LIGHT)


def apply_primary_button(button: QPushButton) -> None:
    button.setObjectName("btnPrimary")


def apply_reminders_button(button: QPushButton) -> None:
    button.setObjectName("btnReminders")


def apply_nav_tree_palette(nav: QTreeWidget, *, dark: bool) -> None:
    """Match native selection colors to our tokens (prevents system-blue branch corners)."""
    pal = nav.palette()
    if dark:
        pal.setColor(QPalette.ColorRole.Highlight, QColor(_ACCENT_SUBTLE_DARK))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(_ACCENT_ON_DARK))
        pal.setColor(QPalette.ColorRole.Base, QColor("#181b24"))
    else:
        pal.setColor(QPalette.ColorRole.Highlight, QColor(_ACCENT_SUBTLE_LIGHT))
        pal.setColor(QPalette.ColorRole.HighlightedText, QColor(_ACCENT_ON_LIGHT))
        pal.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    nav.setPalette(pal)


def _nav_styles(*, dark: bool) -> str:
    if dark:
        page = "#b8c0d4"
        hover = "#1f2433"
        selected_bg = _ACCENT_SUBTLE_DARK
        selected_fg = _ACCENT_ON_DARK
    else:
        page = "#4b5563"
        hover = "#eceef4"
        selected_bg = _ACCENT_SUBTLE_LIGHT
        selected_fg = _ACCENT_ON_LIGHT
    return f"""
    QTreeWidget#appNav {{
        background: transparent;
        border: none;
        outline: none;
        font-size: 13px;
        show-decoration-selected: 0;
    }}
    QTreeWidget#appNav::branch {{
        background: transparent;
        border: none;
    }}
    QTreeWidget#appNav::branch:selected,
    QTreeWidget#appNav::branch:hover {{
        background: transparent;
    }}
    QTreeWidget#appNav::item {{
        padding: 7px 10px;
        border-radius: 6px;
        color: {page};
        border: none;
        outline: none;
    }}
    QTreeWidget#appNav::item:hover {{
        background: {hover};
    }}
    QTreeWidget#appNav::item:selected,
    QTreeWidget#appNav::item:selected:active,
    QTreeWidget#appNav::item:selected:!active,
    QTreeWidget#appNav::item:selected:hover {{
        background-color: {selected_bg};
        color: {selected_fg};
        font-weight: 600;
        border: none;
        outline: none;
    }}
    """


def _input_focus_styles() -> str:
    return f"""
    QLineEdit:focus, QTextEdit:focus, QComboBox:focus, QSpinBox:focus,
    QDoubleSpinBox:focus, QDateEdit:focus {{
        border-color: {_ACCENT};
    }}
    """


def _form_and_table_action_styles(
    *, dark: bool, muted: str, text: str, card: str, border: str
) -> str:
    hover = "#1f2433" if dark else "#eceef4"
    pressed = "#12151e" if dark else "#e5e7eb"
    return f"""
    QLabel#formLabel {{
        background: transparent;
        color: {muted};
        font-weight: 600;
        font-size: 12px;
        padding: 0 16px 0 0;
        border: none;
    }}
    QLabel#formSectionTitle {{
        background: transparent;
        color: {text};
        font-size: 14px;
        font-weight: 700;
        padding: 8px 0 4px;
        border: none;
    }}
    QLabel#formHint {{
        background: transparent;
        color: {muted};
        font-size: 11px;
        border: none;
    }}
    QFrame#formCard QLabel,
    QGroupBox QLabel {{
        background: transparent;
    }}
    QPushButton#btnIconDanger {{
        border: none;
        background: transparent;
        padding: 5px;
        min-width: 30px;
        max-width: 30px;
        min-height: 30px;
        max-height: 30px;
    }}
    QPushButton#btnIconDanger:hover {{
        background: {hover};
        border-radius: 6px;
    }}
    QPushButton#btnIconDanger:pressed {{
        background: {pressed};
    }}
    QPushButton#btnIconDanger:disabled {{
        color: {muted};
    }}
    QPushButton#btnTableAction {{
        border: none;
        background: transparent;
        color: {_ACCENT_ON_LIGHT if not dark else _ACCENT_ON_DARK};
        font-size: 12px;
        font-weight: 600;
        padding: 4px 8px;
        min-height: 28px;
    }}
    QPushButton#btnTableAction:hover {{
        background: {hover};
        border-radius: 6px;
    }}
    QPushButton#btnTableAction:disabled {{
        color: {muted};
    }}
    QWidget#tableActionCell {{
        background: transparent;
    }}
    """


def _scrollbar_styles(*, dark: bool) -> str:
    track = "#1a1f2e" if dark else "#eceef4"
    handle = "#3d4659" if dark else "#c5cad6"
    return f"""
    QScrollBar:vertical {{
        background: transparent;
        width: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {handle};
        border-radius: 4px;
        min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {_ACCENT};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 10px;
        margin: 2px;
    }}
    QScrollBar::handle:horizontal {{
        background: {handle};
        border-radius: 4px;
        min-width: 28px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    """


def _table_styles(*, dark: bool, card: str, border: str, text: str) -> str:
    alt = "#1a1f2e" if dark else "#f0f1f5"
    sel_bg = _ACCENT_SUBTLE_DARK if dark else _ACCENT_SUBTLE_LIGHT
    sel_fg = _ACCENT_ON_DARK if dark else _ACCENT_ON_LIGHT
    return f"""
    QTableWidget {{
        background: {card};
        border: 1px solid {border};
        border-radius: 8px;
        gridline-color: {border};
        color: {text};
        alternate-background-color: {alt};
    }}
    QTableWidget::item {{
        color: {text};
        padding: 4px 2px;
    }}
    QTableWidget::item:alternate {{
        background: {alt};
        color: {text};
    }}
    QTableWidget::item:selected {{
        background: {sel_bg};
        color: {sel_fg};
    }}
    QHeaderView::section {{
        background: {alt};
        padding: 8px;
        border: none;
        border-bottom: 1px solid {border};
        font-weight: 600;
        color: {text};
    }}
    """


def _light_stylesheet() -> str:
    surface = "#f4f5f7"
    card = "#ffffff"
    border = "#e5e7eb"
    text = "#111827"
    muted = "#6b7280"
    return f"""
    QWidget {{
        background: {surface};
        color: {text};
        font-size: 13px;
    }}
    QMainWindow {{
        background: {surface};
    }}
    QWidget#headerBar {{
        background: {card};
        border-bottom: 1px solid {border};
    }}
    QWidget#navPanel {{
        background: {card};
        border-right: 1px solid {border};
    }}
    QWidget#navBrandBlock {{
        background: transparent;
        border-bottom: 1px solid {border};
        margin-bottom: 4px;
    }}
    QLabel#navBrand {{
        font-size: 15px;
        font-weight: 700;
        letter-spacing: -0.3px;
        color: {text};
        padding: 0;
        margin: 0;
        background: transparent;
    }}
    QLabel#navBrandSub {{
        font-size: 11px;
        font-weight: 500;
        color: {muted};
        padding: 0;
        margin: 0;
        background: transparent;
    }}
    QLineEdit#searchInput {{
        background: {surface};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 6px 12px;
        min-height: 34px;
        font-size: 13px;
    }}
    QLineEdit#searchInput:focus {{
        background: {card};
        border-color: {_ACCENT};
    }}
    QLabel {{
        color: {text};
    }}
    QLabel#mutedHint, QLabel#pageSubtitle {{
        color: {muted};
        font-size: 12px;
    }}
    QLabel#pageTitle {{
        font-size: 21px;
        font-weight: 700;
        letter-spacing: -0.4px;
        color: {text};
    }}
    QLabel#dashCardValue {{
        font-size: 22px;
        font-weight: 700;
        color: {text};
    }}
    QLabel#pageSubtitle {{
        font-size: 13px;
        margin-bottom: 2px;
    }}
    QLabel#dashCardCaption {{
        color: {muted};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#dashCardFoot {{
        color: {muted};
        font-size: 13px;
    }}
    QLabel#kpiCaption {{
        color: {muted};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#kpiValue {{
        color: {text};
        font-size: 19px;
        font-weight: 700;
    }}
    QLabel#sectionHeading {{
        font-size: 15px;
        font-weight: 600;
        color: {text};
    }}
    QFrame#contentSection, QFrame#setupSection {{
        background: {card};
        border: 1px solid {border};
        border-radius: 12px;
    }}
    QFrame#contentSection QLabel, QFrame#setupSection QLabel {{
        background: transparent;
        border: none;
    }}
    QLabel#sectionCardTitle {{
        background: transparent;
        color: {text};
        font-size: 15px;
        font-weight: 700;
        padding: 0;
        border: none;
    }}
    QFrame#sectionDivider {{
        background: {border};
        max-height: 1px;
        min-height: 1px;
        border: none;
    }}
    QLabel#analyticsStat {{
        font-size: 14px;
        font-weight: 600;
        color: {text};
    }}
    QFrame#dashCardAlert QLabel#dashCardCaption {{
        color: {_ROSE_LIGHT_TEXT};
    }}
    QFrame#dashCardWarn QLabel#dashCardCaption {{
        color: #92400e;
    }}
    QFrame#dashCardStock QLabel#dashCardCaption {{
        color: #9a3412;
    }}
    QLabel#alertBannerOk {{
        font-size: 13px;
        padding: 10px 12px;
        border-radius: 8px;
        background: #f0fdf4;
        color: #166534;
        border: 1px solid #bbf7d0;
    }}
    QLabel#alertBannerWarn {{
        font-size: 13px;
        padding: 10px 12px;
        border-radius: 8px;
        background: #fff7ed;
        color: #9a3412;
        border: 1px solid #fed7aa;
    }}
    QLabel#alertBannerInfo {{
        font-size: 13px;
        padding: 10px 12px;
        border-radius: 8px;
        background: {_ACCENT_SUBTLE_LIGHT};
        color: {_ACCENT_ON_LIGHT};
        border: 1px solid #c7caff;
    }}
    QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
        background: {card};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 4px 8px;
        color: {text};
        selection-background-color: {_ACCENT};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QPushButton {{
        background: {card};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 6px 14px;
        min-height: 28px;
        color: {text};
    }}
    QPushButton:hover {{
        border-color: #d1d5db;
        background: #f0f1f5;
    }}
    QPushButton:pressed {{
        background: #e5e7eb;
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
    QPushButton#btnPrimary:disabled {{
        background: #94a3b8;
        color: #e2e8f0;
    }}
    QPushButton#btnReminders {{
        background: {_ROSE_LIGHT_BG};
        color: {_ROSE_LIGHT_TEXT};
        border: 1px solid {_ROSE_LIGHT_BORDER};
        font-weight: 600;
    }}
    QPushButton#btnReminders:hover {{
        background: #ffe4e6;
        border-color: #fda4af;
    }}
    {_input_focus_styles()}
    {_form_and_table_action_styles(dark=False, muted=muted, text=text, card=card, border=border)}
    {_nav_styles(dark=False)}
    {_table_styles(dark=False, card=card, border=border, text=text)}
    {_scrollbar_styles(dark=False)}
    QListWidget {{
        background: {card};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 6px;
        color: {text};
    }}
    QListWidget::item:selected {{
        background: {_ACCENT_SUBTLE_LIGHT};
        color: {_ACCENT_ON_LIGHT};
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QGroupBox {{
        font-weight: 600;
        border: 1px solid {border};
        border-radius: 12px;
        margin-top: 14px;
        padding: 16px 14px 12px;
        background: {card};
        color: {text};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        background: {card};
    }}
    QFrame#dashCard {{
        background: {card};
        border: 1px solid {border};
        border-radius: 12px;
        padding: 14px 16px;
    }}
    QFrame#dashCardWarn {{
        background: #fffbeb;
        border: 1px solid #fde68a;
        border-radius: 12px;
        padding: 14px 16px;
    }}
    QFrame#dashCardAlert {{
        background: {_ROSE_LIGHT_BG};
        border: 1px solid {_ROSE_LIGHT_BORDER};
        border-radius: 12px;
        padding: 14px 16px;
    }}
    QFrame#dashCardStock {{
        background: #fff7ed;
        border: 1px solid #fed7aa;
        border-radius: 12px;
        padding: 14px 16px;
    }}
    QFrame#formCard {{
        background: {card};
        border: 1px solid {border};
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 12px;
    }}
    QTabWidget::pane {{
        border: 1px solid {border};
        border-radius: 8px;
        background: {card};
    }}
    QTabBar::tab {{
        background: #f0f1f5;
        border: 1px solid {border};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 8px 14px;
        color: {muted};
    }}
    QTabBar::tab:selected {{
        background: {card};
        color: {text};
        font-weight: 600;
    }}
    QCheckBox {{
        color: {text};
    }}
    """


def _dark_stylesheet() -> str:
    surface = "#0f1117"
    card = "#181b24"
    border = "#2a2f3a"
    text = "#eceef3"
    muted = "#9ca3af"
    return f"""
    QWidget {{
        background: {surface};
        color: {text};
        font-size: 13px;
    }}
    QMainWindow {{
        background: {surface};
    }}
    QWidget#headerBar {{
        background: {card};
        border-bottom: 1px solid {border};
    }}
    QWidget#navPanel {{
        background: {card};
        border-right: 1px solid {border};
    }}
    QWidget#navBrandBlock {{
        background: transparent;
        border-bottom: 1px solid {border};
        margin-bottom: 4px;
    }}
    QLabel#navBrand {{
        font-size: 15px;
        font-weight: 700;
        letter-spacing: -0.3px;
        color: {text};
        padding: 0;
        margin: 0;
        background: transparent;
    }}
    QLabel#navBrandSub {{
        font-size: 11px;
        font-weight: 500;
        color: {muted};
        padding: 0;
        margin: 0;
        background: transparent;
    }}
    QLineEdit#searchInput {{
        background: #12151e;
        border: 1px solid {border};
        border-radius: 8px;
        padding: 6px 12px;
        min-height: 34px;
        font-size: 13px;
    }}
    QLineEdit#searchInput:focus {{
        background: #1a1f2e;
        border-color: {_ACCENT};
    }}
    QLabel {{
        color: {text};
    }}
    QLabel#mutedHint, QLabel#pageSubtitle {{
        color: {muted};
        font-size: 12px;
    }}
    QLabel#pageTitle {{
        font-size: 21px;
        font-weight: 700;
        letter-spacing: -0.4px;
        color: {text};
    }}
    QLabel#dashCardValue {{
        font-size: 22px;
        font-weight: 700;
        color: {text};
    }}
    QLabel#pageSubtitle {{
        font-size: 13px;
        margin-bottom: 2px;
    }}
    QLabel#dashCardCaption {{
        color: {muted};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#dashCardFoot {{
        color: {muted};
        font-size: 13px;
    }}
    QLabel#kpiCaption {{
        color: {muted};
        font-size: 12px;
        font-weight: 600;
    }}
    QLabel#kpiValue {{
        color: {text};
        font-size: 19px;
        font-weight: 700;
    }}
    QLabel#sectionHeading {{
        font-size: 15px;
        font-weight: 600;
        color: {text};
    }}
    QFrame#contentSection, QFrame#setupSection {{
        background: {card};
        border: 1px solid {border};
        border-radius: 12px;
    }}
    QFrame#contentSection QLabel, QFrame#setupSection QLabel {{
        background: transparent;
        border: none;
    }}
    QLabel#sectionCardTitle {{
        background: transparent;
        color: {text};
        font-size: 15px;
        font-weight: 700;
        padding: 0;
        border: none;
    }}
    QFrame#sectionDivider {{
        background: {border};
        max-height: 1px;
        min-height: 1px;
        border: none;
    }}
    QLabel#analyticsStat {{
        font-size: 14px;
        font-weight: 600;
        color: {text};
    }}
    QFrame#dashCardAlert QLabel#dashCardCaption {{
        color: {_ROSE_DARK_TEXT};
    }}
    QFrame#dashCardWarn QLabel#dashCardCaption {{
        color: #fde68a;
    }}
    QFrame#dashCardStock QLabel#dashCardCaption {{
        color: #fdba74;
    }}
    QLabel#alertBannerOk {{
        font-size: 13px;
        padding: 10px 12px;
        border-radius: 8px;
        background: #14532d;
        color: #bbf7d0;
        border: 1px solid #166534;
    }}
    QLabel#alertBannerWarn {{
        font-size: 13px;
        padding: 10px 12px;
        border-radius: 8px;
        background: #422006;
        color: #fde68a;
        border: 1px solid #92400e;
    }}
    QLabel#alertBannerInfo {{
        font-size: 13px;
        padding: 10px 12px;
        border-radius: 8px;
        background: {_ACCENT_SUBTLE_DARK};
        color: {_ACCENT_ON_DARK};
        border: 1px solid #4343b0;
    }}
    QLineEdit, QTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
        background: #12151e;
        border: 1px solid {border};
        border-radius: 6px;
        padding: 4px 8px;
        color: {text};
        selection-background-color: {_ACCENT};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 22px;
    }}
    QPushButton {{
        background: {card};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 6px 14px;
        min-height: 28px;
        color: {text};
    }}
    QPushButton:hover {{
        border-color: #3d4659;
        background: #1f2433;
    }}
    QPushButton:pressed {{
        background: #12151e;
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
    QPushButton#btnReminders {{
        background: {_ROSE_DARK_BG};
        color: {_ROSE_DARK_TEXT};
        border: 1px solid {_ROSE_DARK_BORDER};
        font-weight: 600;
    }}
    QPushButton#btnReminders:hover {{
        background: #881337;
    }}
    {_input_focus_styles()}
    {_form_and_table_action_styles(dark=True, muted=muted, text=text, card=card, border=border)}
    {_nav_styles(dark=True)}
    {_table_styles(dark=True, card=card, border=border, text=text)}
    {_scrollbar_styles(dark=True)}
    QListWidget {{
        background: {card};
        border: 1px solid {border};
        border-radius: 8px;
        padding: 6px;
        color: {text};
    }}
    QListWidget::item:selected {{
        background: {_ACCENT_SUBTLE_DARK};
        color: {_ACCENT_ON_DARK};
    }}
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QGroupBox {{
        font-weight: 600;
        border: 1px solid {border};
        border-radius: 12px;
        margin-top: 14px;
        padding: 16px 14px 12px;
        background: {card};
        color: {text};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        background: {card};
    }}
    QFrame#dashCard {{
        background: {card};
        border: 1px solid {border};
        border-radius: 12px;
        padding: 14px 16px;
    }}
    QFrame#dashCardWarn {{
        background: #422006;
        border: 1px solid #92400e;
        border-radius: 12px;
        padding: 14px 16px;
    }}
    QFrame#dashCardAlert {{
        background: {_ROSE_DARK_BG};
        border: 1px solid {_ROSE_DARK_BORDER};
        border-radius: 12px;
        padding: 14px 16px;
    }}
    QFrame#dashCardStock {{
        background: #431407;
        border: 1px solid #9a3412;
        border-radius: 12px;
        padding: 14px 16px;
    }}
    QFrame#formCard {{
        background: {card};
        border: 1px solid {border};
        border-radius: 12px;
        padding: 14px 16px;
        margin-bottom: 12px;
    }}
    QTabWidget::pane {{
        border: 1px solid {border};
        border-radius: 8px;
        background: {card};
    }}
    QTabBar::tab {{
        background: #0e1729;
        border: 1px solid {border};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 8px 14px;
        color: {muted};
    }}
    QTabBar::tab:selected {{
        background: {card};
        color: {text};
        font-weight: 600;
    }}
    QCheckBox {{
        color: {text};
    }}
    """
