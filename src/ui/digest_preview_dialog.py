from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextEdit,
    QVBoxLayout,
)


class DigestPreviewDialog(QDialog):
    def __init__(self, body: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reminder digest preview")
        self.resize(620, 480)
        self.setMinimumSize(520, 360)

        layout = QVBoxLayout(self)
        cap = QLabel("This is the email body that would be sent:")
        cap.setStyleSheet("color:#475569; font-size:13px;")
        layout.addWidget(cap)

        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(body)
        editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        font = QFont("Consolas")
        if not font.exactMatch():
            font = QFont("Courier New")
        editor.setFont(font)
        layout.addWidget(editor, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
