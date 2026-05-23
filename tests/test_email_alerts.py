from __future__ import annotations

import os
from pathlib import Path

from src.db.conn import connect
from src.db.migrate import migrate
from datetime import date

from src.email_alerts import (
    SETTING_EMAIL_ON_SIGNIN,
    SETTING_LAST_DIGEST_DATE,
    SETTING_OWNER_EMAIL,
    load_dotenv,
    maybe_send_signin_digest,
    owner_recipient,
    smtp_config_status,
)
from src.repo import Repo


def test_owner_recipient_prefers_settings(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OWNER_EMAIL", raising=False)
    conn = connect(tmp_path / "mail.db")
    migrate(conn)
    repo = Repo(conn)
    repo.set_setting(SETTING_OWNER_EMAIL, "owner@example.com")
    assert owner_recipient(repo) == "owner@example.com"


def test_smtp_config_status_missing_env(tmp_path: Path, monkeypatch) -> None:
    for key in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS", "OWNER_EMAIL"):
        monkeypatch.delenv(key, raising=False)
    conn = connect(tmp_path / "smtp.db")
    migrate(conn)
    repo = Repo(conn)
    load_dotenv(tmp_path / "nonexistent.env")
    ok, msg = smtp_config_status(repo)
    assert not ok
    assert "Missing" in msg


def test_signin_digest_skips_when_disabled(tmp_path: Path) -> None:
    conn = connect(tmp_path / "signin.db")
    migrate(conn)
    repo = Repo(conn)
    sent, msg = maybe_send_signin_digest(repo, date(2026, 5, 22))
    assert not sent
    assert "off" in msg.lower()


def test_signin_digest_skips_when_already_sent_today(tmp_path: Path) -> None:
    conn = connect(tmp_path / "signin2.db")
    migrate(conn)
    repo = Repo(conn)
    repo.set_setting(SETTING_EMAIL_ON_SIGNIN, "1")
    repo.set_setting(SETTING_LAST_DIGEST_DATE, "2026-05-22")
    sent, msg = maybe_send_signin_digest(repo, date(2026, 5, 22))
    assert not sent
    assert "Already" in msg
