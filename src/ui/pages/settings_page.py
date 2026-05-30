from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from datetime import date

from ...backup import backup_sqlite_database, backups_dir_for_db
from ...db.conn import transaction
from ...email_alerts import (
    SETTING_EMAIL_ON_SIGNIN,
    SETTING_LAST_DIGEST_DATE,
    SETTING_OWNER_EMAIL,
    load_dotenv,
    send_owner_reminder_email,
    smtp_config_status,
)
from ...owner_digest import build_owner_digest
from ..digest_preview_dialog import DigestPreviewDialog
from ..form_util import configure_form, form_add_row, form_section_title
from ..page_header import make_page_header
from ..theme import apply_primary_button
from ...paths import get_paths
from ...repo import Repo


class SettingsPage(QWidget):
    saved = Signal()

    def __init__(self, repo: Repo) -> None:
        super().__init__()
        self._repo = repo

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        outer.addWidget(scroll, 1)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        scroll.setWidget(inner)

        layout.addWidget(
            make_page_header(
                "Settings",
                "Invoice template paths, owner email digests, and database backup.",
            )
        )

        form = QFormLayout()
        configure_form(form)

        self.default_credit_days = QLineEdit()
        self.default_credit_days.setMinimumHeight(32)
        self.default_credit_days.setPlaceholderText("45")
        form_add_row(form, "Default credit days", self.default_credit_days)

        # Phase 2 dependencies
        self.template_path = QLineEdit()
        self.template_path.setMinimumHeight(32)
        pick_tpl = QHBoxLayout()
        pick_tpl.addWidget(self.template_path, 1)
        self.btn_pick_tpl = QPushButton("Choose…")
        self.btn_pick_tpl.setMinimumHeight(32)
        pick_tpl.addWidget(self.btn_pick_tpl)
        form_add_row(form, "Invoice template (.xlsx)", pick_tpl)

        self.output_folder = QLineEdit()
        self.output_folder.setMinimumHeight(32)
        pick_out = QHBoxLayout()
        pick_out.addWidget(self.output_folder, 1)
        self.btn_pick_out = QPushButton("Choose…")
        self.btn_pick_out.setMinimumHeight(32)
        pick_out.addWidget(self.btn_pick_out)
        form_add_row(form, "Invoice output folder", pick_out)

        layout.addLayout(form)

        layout.addWidget(form_section_title("Email reminders (owner)"))
        env_hint = QLabel(
            "SMTP login lives in a .env file (copy .env.example → .env). "
            "Use a Gmail App Password, not your normal password."
        )
        env_hint.setWordWrap(True)
        env_hint.setStyleSheet("color:#64748b; font-size:12px;")
        layout.addWidget(env_hint)

        alert_form = QFormLayout()
        configure_form(alert_form)
        self.owner_alert_email = QLineEdit()
        self.owner_alert_email.setMinimumHeight(32)
        self.owner_alert_email.setPlaceholderText("your.email@gmail.com")
        form_add_row(alert_form, "Send reminders to", self.owner_alert_email)
        layout.addLayout(alert_form)

        self.chk_email_on_signin = QCheckBox(
            "Email digest when I sign in (at most once per day)"
        )
        self.chk_email_on_signin.setStyleSheet("font-size:13px;")
        layout.addWidget(self.chk_email_on_signin)

        self._smtp_status = QLabel("")
        self._smtp_status.setWordWrap(True)
        self._smtp_status.setStyleSheet("color:#475569; font-size:12px;")
        layout.addWidget(self._smtp_status)

        alert_btns = QHBoxLayout()
        self.btn_preview_digest = QPushButton("Preview digest")
        self.btn_preview_digest.setMinimumHeight(34)
        self.btn_send_digest = QPushButton("Send email now")
        self.btn_send_digest.setMinimumHeight(36)
        apply_primary_button(self.btn_send_digest)
        alert_btns.addWidget(self.btn_preview_digest)
        alert_btns.addWidget(self.btn_send_digest)
        alert_btns.addStretch(1)
        layout.addLayout(alert_btns)

        schedule_hint = QLabel(
            "If the PC is not on at a fixed time: turn on sign-in email above, or run "
            "Send email now when you open the app. Task Scheduler only works while the PC is on."
        )
        schedule_hint.setWordWrap(True)
        schedule_hint.setStyleSheet("color:#64748b; font-size:12px;")
        layout.addWidget(schedule_hint)

        safety = QLabel("Data safety")
        safety.setStyleSheet("font-size:15px; font-weight:600; margin-top:14px;")
        layout.addWidget(safety)
        self.db_path_label = QLabel()
        self.db_path_label.setWordWrap(True)
        self.db_path_label.setStyleSheet("color:#475569; font-size:12px;")
        layout.addWidget(self.db_path_label)
        backup_row = QHBoxLayout()
        self.btn_backup_db = QPushButton("Back up database now")
        self.btn_backup_db.setMinimumHeight(34)
        self.btn_open_backups = QPushButton("Open backups folder")
        self.btn_open_backups.setMinimumHeight(34)
        backup_row.addWidget(self.btn_backup_db)
        backup_row.addWidget(self.btn_open_backups)
        backup_row.addStretch(1)
        layout.addLayout(backup_row)
        hint_bak = QLabel(
            "Creates a timestamped copy under data/backups using SQLite’s backup API (safe while the app is running)."
        )
        hint_bak.setWordWrap(True)
        hint_bak.setStyleSheet("color:#64748b; font-size:12px;")
        layout.addWidget(hint_bak)

        self.btn_save = QPushButton("Save Settings")
        self.btn_save.setMinimumHeight(38)
        apply_primary_button(self.btn_save)
        layout.addWidget(self.btn_save)
        layout.addStretch(1)

        self.btn_pick_tpl.clicked.connect(self._pick_template)
        self.btn_pick_out.clicked.connect(self._pick_output)
        self.btn_save.clicked.connect(self._save)
        self.btn_backup_db.clicked.connect(self._backup_database)
        self.btn_open_backups.clicked.connect(self._open_backups_folder)
        self.btn_preview_digest.clicked.connect(self._preview_digest)
        self.btn_send_digest.clicked.connect(self._send_digest_email)

        self.load()

    def load(self) -> None:
        paths = get_paths()
        self.db_path_label.setText(f"Active database:\n{paths.db_path}")
        self.default_credit_days.setText(self._repo.get_setting("default_credit_days", "45"))
        # Prefer bundled template path if user hasn't set one.
        bundled = str(get_paths().root / "assets" / "invoice_template.xlsx")
        tpl = self._repo.get_setting("invoice_template_path", "").strip() or bundled
        self.template_path.setText(tpl)
        # Default output folder: PersonalizedTally\invoices\<FY>\  (good structure long-term)
        today = __import__("datetime").date.today()
        fy = today.year if today.month >= 4 else (today.year - 1)
        default_out = str(get_paths().root / "invoices" / f"{fy}-{fy+1}")
        self.output_folder.setText(self._repo.get_setting("invoice_output_folder", default_out))
        self.owner_alert_email.setText(self._repo.get_setting(SETTING_OWNER_EMAIL, ""))
        self.chk_email_on_signin.setChecked(
            self._repo.get_setting(SETTING_EMAIL_ON_SIGNIN, "").strip() == "1"
        )
        self._refresh_smtp_status()

    def _refresh_smtp_status(self) -> None:
        load_dotenv(get_paths().root / ".env")
        ok, msg = smtp_config_status(self._repo)
        self._smtp_status.setText(msg)
        self._smtp_status.setStyleSheet(
            "color:#166534; font-size:12px;" if ok else "color:#b45309; font-size:12px;"
        )

    def _pick_template(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select invoice template", filter="Excel (*.xlsx)")
        if path:
            self.template_path.setText(path)

    def _pick_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select invoice output folder")
        if folder:
            self.output_folder.setText(folder)

    def _save(self) -> None:
        try:
            credit_days = int(self.default_credit_days.text().strip() or "45")
            if credit_days <= 0 or credit_days > 3650:
                raise ValueError("Default credit days must be between 1 and 3650")
        except Exception as e:
            QMessageBox.warning(self, "Invalid", str(e))
            return

        tpl_p = self.template_path.text().strip()
        out_p = self.output_folder.text().strip()
        owner_mail = self.owner_alert_email.text().strip()
        with transaction(self._repo.conn):
            self._repo.set_setting("default_credit_days", str(credit_days))
            self._repo.set_setting("invoice_template_path", tpl_p)
            self._repo.set_setting("invoice_output_folder", out_p)
            self._repo.set_setting(SETTING_OWNER_EMAIL, owner_mail)
            self._repo.set_setting(
                SETTING_EMAIL_ON_SIGNIN,
                "1" if self.chk_email_on_signin.isChecked() else "0",
            )
            self._repo.audit_log_append(
                action="settings_saved",
                entity_type="settings",
                entity_id=None,
                detail=(
                    f"default_credit_days={credit_days}; "
                    f"invoice_template_path_len={len(tpl_p)}; "
                    f"invoice_output_folder_len={len(out_p)}"
                ),
            )

        # Create output folder if missing.
        try:
            from pathlib import Path

            Path(self.output_folder.text().strip()).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        QMessageBox.information(self, "Saved", "Settings saved.")
        self._refresh_smtp_status()
        self.saved.emit()

    def _preview_digest(self) -> None:
        text = build_owner_digest(self._repo, date.today())
        dlg = DigestPreviewDialog(text, self)
        dlg.exec()

    def _send_digest_email(self) -> None:
        owner_mail = self.owner_alert_email.text().strip()
        if owner_mail:
            self._repo.set_setting(SETTING_OWNER_EMAIL, owner_mail)
        load_dotenv(get_paths().root / ".env")
        ok, msg = smtp_config_status(self._repo)
        if not ok:
            QMessageBox.warning(self, "Email not configured", msg)
            return
        try:
            today = date.today()
            to, _ = send_owner_reminder_email(self._repo, today)
            self._repo.set_setting(SETTING_LAST_DIGEST_DATE, today.isoformat())
        except Exception as e:
            QMessageBox.critical(self, "Send failed", str(e))
            return
        QMessageBox.information(
            self,
            "Email sent",
            f"Reminder digest sent to:\n{to}",
        )

    def _backup_database(self) -> None:
        try:
            dest = backup_sqlite_database(self._repo.conn)
        except Exception as e:
            QMessageBox.critical(self, "Backup failed", str(e))
            return
        QMessageBox.information(
            self,
            "Backup created",
            f"Database backup saved to:\n{dest}",
        )

    def _open_backups_folder(self) -> None:
        folder = backups_dir_for_db(get_paths().db_path)
        folder.mkdir(parents=True, exist_ok=True)
        path = str(folder.resolve())
        try:
            if sys.platform == "win32":
                subprocess.run(["explorer", path], check=False)
            elif sys.platform == "darwin":
                subprocess.run(["open", path], check=False)
            else:
                subprocess.run(["xdg-open", path], check=False)
        except Exception as e:
            QMessageBox.warning(self, "Open folder", f"Could not open folder:\n{e}\n\nPath:\n{path}")

