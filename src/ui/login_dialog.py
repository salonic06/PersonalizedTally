from __future__ import annotations

from typing import Literal, cast

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from ..app_info import APP_DISPLAY_NAME
from ..repo import Repo
from .form_util import configure_form, form_add_row

Role = Literal["owner", "worker"]


class LoginDialog(QDialog):
    def __init__(self, repo: Repo, parent=None) -> None:
        super().__init__(parent)
        self._repo = repo
        self._username_out = ""
        self._role_out: Role = "worker"

        self.setWindowTitle(f"Sign in — {APP_DISPLAY_NAME}")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        title = QLabel(APP_DISPLAY_NAME)
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        intro = QLabel("Sign in to continue.")
        intro.setObjectName("mutedHint")
        layout.addWidget(intro)
        form = QFormLayout()
        configure_form(form)
        self.user = QLineEdit()
        self.user.setPlaceholderText("Username")
        self.pw = QLineEdit()
        self.pw.setEchoMode(QLineEdit.EchoMode.Password)
        self.pw.setPlaceholderText("Password")
        form_add_row(form, "Username", self.user)
        form_add_row(form, "Password", self.pw)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._try_login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.user.returnPressed.connect(self.pw.setFocus)
        self.pw.returnPressed.connect(self._try_login)

        self.user.setMinimumWidth(320)
        self.adjustSize()

    def _try_login(self) -> None:
        u = self.user.text().strip()
        p = self.pw.text()
        role = self._repo.verify_login(u, p)
        if role not in ("owner", "worker"):
            QMessageBox.warning(self, "Sign in", "Unknown username or wrong password.")
            return
        self._username_out = u
        self._role_out = cast(Role, role)
        self.accept()

    def credentials(self) -> tuple[str, Role]:
        return self._username_out, self._role_out
