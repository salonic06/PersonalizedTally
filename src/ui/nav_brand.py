"""Sidebar app title block — layout avoids QLabel negative-margin clipping."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def make_nav_brand(title: str, subtitle: str = "") -> QWidget:
    block = QWidget()
    block.setObjectName("navBrandBlock")
    lay = QVBoxLayout(block)
    if subtitle.strip():
        lay.setContentsMargins(10, 6, 10, 12)
        lay.setSpacing(3)
    else:
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(0)
    head = QLabel(title)
    head.setObjectName("navBrand")
    head.setWordWrap(False)
    lay.addWidget(head)
    if subtitle.strip():
        sub = QLabel(subtitle.strip())
        sub.setObjectName("navBrandSub")
        sub.setWordWrap(True)
        lay.addWidget(sub)
    return block
