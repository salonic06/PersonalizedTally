from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from ..repo import Repo
from .form_util import configure_form, form_add_row


class ChangePasswordDialog(QDialog):
    def __init__(self, repo: Repo, username: str, parent=None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._username = (username or "").strip()

        self.setWindowTitle("Change password")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Signed in as {self._username}"))

        form = QFormLayout()
        configure_form(form)
        self.old_pw = QLineEdit()
        self.old_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.old_pw.setPlaceholderText("Current password")
        self.new_pw = QLineEdit()
        self.new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_pw.setPlaceholderText("New password (min 6 characters)")
        self.new_pw2 = QLineEdit()
        self.new_pw2.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_pw2.setPlaceholderText("Confirm new password")
        for w in (self.old_pw, self.new_pw, self.new_pw2):
            w.setMinimumHeight(32)
        form_add_row(form, "Current", self.old_pw)
        form_add_row(form, "New", self.new_pw)
        form_add_row(form, "Confirm", self.new_pw2)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._try_change)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.old_pw.returnPressed.connect(self.new_pw.setFocus)
        self.new_pw.returnPressed.connect(self.new_pw2.setFocus)
        self.new_pw2.returnPressed.connect(self._try_change)

        self.setMinimumWidth(360)

    def _try_change(self) -> None:
        if not self._username:
            QMessageBox.warning(self, "Change password", "No username in session.")
            return
        old_p = self.old_pw.text()
        n1 = self.new_pw.text()
        n2 = self.new_pw2.text()
        if n1 != n2:
            QMessageBox.warning(self, "Change password", "New password and confirmation do not match.")
            return
        try:
            self._repo.update_own_password(self._username, old_p, n1)
        except ValueError as e:
            QMessageBox.warning(self, "Change password", str(e))
            return
        QMessageBox.information(self, "Change password", "Password updated. Use it next time you sign in.")
        self.accept()
