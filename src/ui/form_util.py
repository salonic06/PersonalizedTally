"""Form layouts — transparent labels (no Fusion label-column shading)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QLayout, QVBoxLayout, QWidget


def configure_form(layout: QFormLayout) -> None:
    layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    layout.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    layout.setHorizontalSpacing(20)
    layout.setVerticalSpacing(12)
    layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)


def form_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("formLabel")
    lbl.setAutoFillBackground(False)
    return lbl


def form_section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("formSectionTitle")
    lbl.setAutoFillBackground(False)
    return lbl


def form_hint(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("formHint")
    lbl.setWordWrap(True)
    lbl.setAutoFillBackground(False)
    return lbl


def _wrap_layout(field: QWidget | QLayout) -> QWidget:
    if isinstance(field, QWidget):
        return field
    wrap = QWidget()
    wrap.setLayout(field)
    return wrap


def form_add_row(layout: QFormLayout, label: str, field: QWidget | QLayout) -> None:
    """Add a labeled row; label column has no background fill."""
    layout.addRow(form_label(label), _wrap_layout(field))


def form_add_widget_row(layout: QFormLayout, field: QWidget | QLayout) -> None:
    """Full-width row spanning both columns."""
    layout.addRow(_wrap_layout(field))


def form_add_title_row(layout: QFormLayout, title: str) -> None:
    layout.addRow(form_section_title(title))
