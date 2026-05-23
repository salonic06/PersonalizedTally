from __future__ import annotations

from datetime import date

from .notifications import AppNotification, collect_notifications
from .repo import Repo


def format_owner_digest(
    notifications: list[AppNotification],
    *,
    today: date | None = None,
    app_name: str = "Personalized Tally",
) -> str:
    """Plain-text summary for owner email digest."""
    ref = today or date.today()
    lines = [f"{app_name} — reminders for {ref.strftime('%d %b %Y')}", ""]

    if not notifications:
        lines.append("All clear: no low stock, due today, or overdue invoices.")
        return "\n".join(lines)

    for n in notifications:
        lines.append(n.title)
        lines.append(n.detail)
        lines.append("")

    lines.append("(Sent automatically; open the desktop app for details.)")
    return "\n".join(lines).rstrip() + "\n"


def build_owner_digest(repo: Repo, today: date | None = None) -> str:
    ref = today or date.today()
    return format_owner_digest(collect_notifications(repo, ref), today=ref)
