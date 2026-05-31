from __future__ import annotations

import os
import smtplib
import ssl
from datetime import date
from email.message import EmailMessage
from pathlib import Path
from typing import Literal

from .owner_digest import build_owner_digest
from .paths import get_paths
from .repo import Repo

SETTING_OWNER_EMAIL = "owner_alert_email"
SETTING_EMAIL_ON_SIGNIN = "owner_email_on_signin"
SETTING_LAST_DIGEST_DATE = "owner_digest_last_sent_date"

DigestSource = Literal["signin", "manual", "unknown"]


def project_root() -> Path:
    return get_paths().root


def load_dotenv(path: Path | None = None) -> None:
    p = path or (project_root() / ".env")
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def owner_recipient(repo: Repo) -> str:
    from_db = repo.get_setting(SETTING_OWNER_EMAIL, "").strip()
    if from_db:
        return from_db
    return _env("OWNER_EMAIL")


def smtp_config_status(repo: Repo) -> tuple[bool, str]:
    """Return (ready, message). Call load_dotenv() first."""
    missing = []
    for name, val in [
        ("SMTP_HOST", _env("SMTP_HOST")),
        ("SMTP_USER", _env("SMTP_USER")),
        ("SMTP_PASS", _env("SMTP_PASS")),
    ]:
        if not val:
            missing.append(name)
    to = owner_recipient(repo)
    if not to:
        missing.append(f"{SETTING_OWNER_EMAIL} (Settings) or OWNER_EMAIL (.env)")
    if missing:
        return False, "Missing: " + ", ".join(missing) + ". Copy .env.example to .env."
    return True, f"Will send to {to} via {_env('SMTP_HOST')}"


def send_email_digest(
    *,
    subject: str,
    body: str,
    to_address: str | None = None,
) -> str:
    """Send plain-text email. Returns recipient address. Raises on misconfiguration or SMTP error."""
    load_dotenv()
    host = _env("SMTP_HOST")
    port_s = _env("SMTP_PORT", "587")
    user = _env("SMTP_USER")
    password = _env("SMTP_PASS")
    mail_from = _env("SMTP_FROM", user)
    mail_to = (to_address or _env("OWNER_EMAIL")).strip()

    missing = [n for n, v in [
        ("SMTP_HOST", host),
        ("SMTP_USER", user),
        ("SMTP_PASS", password),
        ("recipient", mail_to),
    ] if not v]
    if missing:
        raise ValueError("Missing: " + ", ".join(missing) + ". See .env.example.")

    try:
        port = int(port_s)
    except ValueError as e:
        raise ValueError("SMTP_PORT must be a number (usually 587).") from e

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = mail_to
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=60) as smtp:
        smtp.ehlo()
        if port != 25:
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(user, password)
        smtp.send_message(msg)
    return mail_to


def send_owner_reminder_email(
    repo: Repo,
    today: date | None = None,
    *,
    source: DigestSource = "unknown",
) -> tuple[str, str]:
    """Build digest from Reminders and email the owner. Returns (recipient, body)."""
    ref = today or date.today()
    body = build_owner_digest(repo, ref)
    subject = f"Personalized Tally reminders — {ref.isoformat()}"
    to = send_email_digest(subject=subject, body=body, to_address=owner_recipient(repo))
    repo.audit_log_append(
        action="digest_email_sent",
        entity_type="email_digest",
        detail=f"source={source} ref={ref.isoformat()} to={to}",
    )
    return to, body


def signin_digest_enabled(repo: Repo) -> bool:
    return repo.get_setting(SETTING_EMAIL_ON_SIGNIN, "").strip() == "1"


def maybe_send_signin_digest(repo: Repo, today: date | None = None) -> tuple[bool, str]:
    """
    If enabled in Settings, email at most once per calendar day when owner signs in.
    Returns (sent, message). Does not raise on SMTP errors — message explains outcome.
    """
    if not signin_digest_enabled(repo):
        return False, "Sign-in email is off in Settings."

    ref = today or date.today()
    iso = ref.isoformat()
    if repo.get_setting(SETTING_LAST_DIGEST_DATE, "").strip() == iso:
        return False, "Already sent today."

    load_dotenv()
    ok, msg = smtp_config_status(repo)
    if not ok:
        return False, msg

    try:
        to, _ = send_owner_reminder_email(repo, ref, source="signin")
    except Exception as e:
        repo.audit_log_append(
            action="digest_email_failed",
            entity_type="email_digest",
            detail=f"source=signin ref={ref.isoformat()} error={e}",
        )
        return False, str(e)

    repo.set_setting(SETTING_LAST_DIGEST_DATE, iso)
    return True, f"Reminder email sent to {to}."
