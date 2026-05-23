"""
Send owner reminder digest by email (same content as in-app Reminders).

Setup: copy .env.example to .env, set owner email in Settings or OWNER_EMAIL in .env.

  python tools/send_owner_digest.py --dry-run
  python tools/send_owner_digest.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.db.conn import connect  # noqa: E402
from src.db.migrate import migrate  # noqa: E402
from src.email_alerts import load_dotenv, send_owner_reminder_email  # noqa: E402
from src.owner_digest import build_owner_digest  # noqa: E402
from src.paths import get_paths  # noqa: E402
from src.repo import Repo  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Email Personalized Tally reminders to the owner.")
    ap.add_argument("--dry-run", action="store_true", help="Print digest only; do not send.")
    args = ap.parse_args()

    load_dotenv(ROOT / ".env")
    paths = get_paths()
    conn = connect(paths.db_path)
    migrate(conn)
    repo = Repo(conn)
    today = date.today()

    if args.dry_run:
        print(build_owner_digest(repo, today))
        print("--- dry-run: nothing sent ---")
        conn.close()
        return 0

    try:
        to, _ = send_owner_reminder_email(repo, today)
    except Exception as e:
        print(f"Failed: {e}", file=sys.stderr)
        conn.close()
        return 1

    print(f"Email sent to {to}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
