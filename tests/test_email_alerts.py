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
    send_owner_reminder_email,
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


def test_send_owner_reminder_email_writes_audit_log(tmp_path: Path, monkeypatch) -> None:
    conn = connect(tmp_path / "audit_mail.db")
    migrate(conn)
    repo = Repo(conn)

    def fake_send(**kwargs):
        return "owner@example.com"

    monkeypatch.setattr("src.email_alerts.send_email_digest", fake_send)

    to, _ = send_owner_reminder_email(repo, date(2026, 5, 22), source="manual")
    assert to == "owner@example.com"

    rows = repo.list_audit_log(limit=10)
    assert len(rows) == 1
    assert rows[0].action == "digest_email_sent"
    assert rows[0].entity_type == "email_digest"
    assert "source=manual" in rows[0].detail
    assert "owner@example.com" in rows[0].detail


def test_signin_digest_failure_writes_audit_log(tmp_path: Path, monkeypatch) -> None:
    conn = connect(tmp_path / "audit_fail.db")
    migrate(conn)
    repo = Repo(conn)
    repo.set_setting(SETTING_EMAIL_ON_SIGNIN, "1")
    repo.set_setting(SETTING_OWNER_EMAIL, "owner@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "user")
    monkeypatch.setenv("SMTP_PASS", "pass")

    def boom(*args, **kwargs):
        raise RuntimeError("smtp down")

    monkeypatch.setattr("src.email_alerts.send_owner_reminder_email", boom)

    sent, msg = maybe_send_signin_digest(repo, date(2026, 5, 22))
    assert not sent
    assert "smtp down" in msg

    rows = [r for r in repo.list_audit_log(limit=10) if r.action == "digest_email_failed"]
    assert len(rows) == 1
    assert rows[0].entity_type == "email_digest"
    assert "source=signin" in rows[0].detail
