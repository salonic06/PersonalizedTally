"""Form layouts and themed section / metric card helpers."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QFrame, QHBoxLayout, QLabel, QLayout, QVBoxLayout, QWidget


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


def section_card_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("sectionCardTitle")
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


def _refresh_widget_style(widget: QWidget) -> None:
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def form_add_row(layout: QFormLayout, label: str, field: QWidget | QLayout) -> None:
    """Add a labeled row; label column has no background fill."""
    layout.addRow(form_label(label), _wrap_layout(field))


def form_add_widget_row(layout: QFormLayout, field: QWidget | QLayout) -> None:
    """Full-width row spanning both columns."""
    layout.addRow(_wrap_layout(field))


def form_add_title_row(layout: QFormLayout, title: str) -> None:
    layout.addRow(form_section_title(title))


def _section_divider() -> QFrame:
    line = QFrame()
    line.setObjectName("sectionDivider")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


def make_setup_section(title: str, subtitle: str = "") -> tuple[QFrame, QFormLayout]:
    """Bordered Setup card with title, optional hint, divider, and form layout."""
    frame = QFrame()
    frame.setObjectName("setupSection")

    outer = QVBoxLayout(frame)
    outer.setContentsMargins(18, 16, 18, 18)
    outer.setSpacing(10)
    outer.addWidget(section_card_title(title))
    if subtitle.strip():
        outer.addWidget(form_hint(subtitle))
    outer.addWidget(_section_divider())

    form_host = QWidget()
    form_host.setAutoFillBackground(False)
    form = QFormLayout(form_host)
    configure_form(form)
    outer.addWidget(form_host)
    return frame, form


def make_content_section(title: str, subtitle: str = "") -> tuple[QFrame, QVBoxLayout]:
    """Bordered content card with title, optional hint, divider, and body layout."""
    frame = QFrame()
    frame.setObjectName("contentSection")

    outer = QVBoxLayout(frame)
    outer.setContentsMargins(18, 16, 18, 18)
    outer.setSpacing(10)
    outer.addWidget(section_card_title(title))
    if subtitle.strip():
        outer.addWidget(form_hint(subtitle))
    outer.addWidget(_section_divider())

    body = QVBoxLayout()
    body.setSpacing(12)
    outer.addLayout(body)
    return frame, body


def make_metric_card(caption: str) -> tuple[QLabel, QLabel, QLabel, QFrame]:
    """KPI tile: caption, value, optional footnote — styled via theme dashCard tokens."""
    box = QFrame()
    box.setObjectName("dashCard")
    box.setMinimumHeight(84)

    vl = QVBoxLayout(box)
    vl.setContentsMargins(12, 10, 12, 10)
    vl.setSpacing(4)

    cap = QLabel(caption)
    cap.setObjectName("dashCardCaption")
    cap.setWordWrap(True)
    val = QLabel("—")
    val.setObjectName("dashCardValue")
    foot = QLabel("")
    foot.setObjectName("dashCardFoot")
    foot.setWordWrap(True)
    vl.addWidget(cap)
    vl.addWidget(val)
    vl.addWidget(foot)
    return val, foot, cap, box


def set_metric_card_style(
    box: QFrame,
    val: QLabel,
    *,
    warn: bool = False,
    alert: bool = False,
    stock: bool = False,
) -> None:
    """Apply attention styling; value color comes from theme objectName rules."""
    if alert:
        box.setObjectName("dashCardAlert")
    elif warn:
        box.setObjectName("dashCardWarn")
    elif stock:
        box.setObjectName("dashCardStock")
    else:
        box.setObjectName("dashCard")
    val.setObjectName("dashCardValue")
    val.setStyleSheet("")
    _refresh_widget_style(box)
