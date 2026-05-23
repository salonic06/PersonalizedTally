"""Consistent page title + subtitle for feature screens."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def make_page_header(title: str, subtitle: str = "") -> QWidget:
    box = QWidget()
    lay = QVBoxLayout(box)
    lay.setContentsMargins(0, 0, 0, 10)
    lay.setSpacing(4)
    t = QLabel(title)
    t.setObjectName("pageTitle")
    lay.addWidget(t)
    if subtitle.strip():
        s = QLabel(subtitle.strip())
        s.setObjectName("pageSubtitle")
        s.setWordWrap(True)
        lay.addWidget(s)
    return box
