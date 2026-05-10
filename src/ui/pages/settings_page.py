from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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

from ...backup import backup_sqlite_database, backups_dir_for_db
from ...db.conn import transaction
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

        title = QLabel("Settings")
        title.setStyleSheet("font-size:20px; font-weight:600;")
        layout.addWidget(title)

        form = QFormLayout()

        self.default_credit_days = QLineEdit()
        self.default_credit_days.setMinimumHeight(32)
        self.default_credit_days.setPlaceholderText("45")
        form.addRow("Default credit days", self.default_credit_days)

        # Phase 2 dependencies
        self.template_path = QLineEdit()
        self.template_path.setMinimumHeight(32)
        pick_tpl = QHBoxLayout()
        pick_tpl.addWidget(self.template_path, 1)
        self.btn_pick_tpl = QPushButton("Choose…")
        self.btn_pick_tpl.setMinimumHeight(32)
        pick_tpl.addWidget(self.btn_pick_tpl)
        form.addRow("Invoice template (.xlsx)", pick_tpl)

        self.output_folder = QLineEdit()
        self.output_folder.setMinimumHeight(32)
        pick_out = QHBoxLayout()
        pick_out.addWidget(self.output_folder, 1)
        self.btn_pick_out = QPushButton("Choose…")
        self.btn_pick_out.setMinimumHeight(32)
        pick_out.addWidget(self.btn_pick_out)
        form.addRow("Invoice output folder", pick_out)

        layout.addLayout(form)

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
        self.btn_save.setMinimumHeight(36)
        layout.addWidget(self.btn_save)
        layout.addStretch(1)

        self.btn_pick_tpl.clicked.connect(self._pick_template)
        self.btn_pick_out.clicked.connect(self._pick_output)
        self.btn_save.clicked.connect(self._save)
        self.btn_backup_db.clicked.connect(self._backup_database)
        self.btn_open_backups.clicked.connect(self._open_backups_folder)

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
        with transaction(self._repo.conn):
            self._repo.set_setting("default_credit_days", str(credit_days))
            self._repo.set_setting("invoice_template_path", tpl_p)
            self._repo.set_setting("invoice_output_folder", out_p)
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
        self.saved.emit()

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

