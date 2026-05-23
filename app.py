from __future__ import annotations

import sys

from PySide6.QtWidgets import QDialog, QMessageBox

from src.audit_context import set_audit_operator_override
from src.email_alerts import maybe_send_signin_digest
from src.db.conn import connect
from src.db.migrate import migrate
from src.paths import get_paths
from src.repo import Repo
from src.ui.login_dialog import LoginDialog
from src.ui.main_window import MainWindow
from src.ui.qt_app import build_qt_app
from src.ui.window_geometry import apply_main_window_state


def main() -> int:
    app = build_qt_app()
    paths = get_paths()
    conn = connect(paths.db_path)
    migrate(conn)
    repo = Repo(conn)

    exit_code = 0
    try:
        while True:
            MainWindow.wants_relogin = False
            set_audit_operator_override(None)

            dlg = LoginDialog(repo)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                break

            username, role = dlg.credentials()
            set_audit_operator_override(username)

            if role == "owner":
                sent, signin_msg = maybe_send_signin_digest(repo)
                if sent:
                    QMessageBox.information(
                        None,
                        "Email sent",
                        signin_msg,
                    )

            window = MainWindow(repo=repo, role=role, username=username)
            apply_main_window_state(window)

            exit_code = app.exec()

            if not MainWindow.wants_relogin:
                break
    finally:
        conn.close()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
