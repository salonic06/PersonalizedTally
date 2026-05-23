from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from .repo import DueRow, Repo

NotificationKind = Literal["reorder_low", "due_today", "overdue"]
NotificationSeverity = Literal["info", "warning", "critical"]
NavAction = Literal["open_due_today", "open_overdue", "open_raw_materials", "none"]


@dataclass(frozen=True)
class AppNotification:
    kind: NotificationKind
    severity: NotificationSeverity
    title: str
    detail: str
    nav_action: NavAction = "none"
    action_label: str = "Open screen"


def _fmt_inr(amount: float) -> str:
    return f"₹{amount:,.0f}"


def _due_today_lines(rows: list[DueRow], *, max_lines: int = 8) -> str:
    lines = [
        f"  • {r.invoice_no} — {r.customer_name} — {_fmt_inr(r.outstanding)}"
        for r in rows[:max_lines]
    ]
    if len(rows) > max_lines:
        lines.append(f"  • +{len(rows) - max_lines} more")
    return "\n".join(lines)


def _overdue_lines(rows: list[DueRow], *, max_lines: int = 8) -> str:
    lines: list[str] = []
    for r in rows[:max_lines]:
        days = r.days_overdue
        suffix = f" · {days} day{'s' if days != 1 else ''}"
        lines.append(
            f"  • {r.invoice_no} — {r.customer_name} — {_fmt_inr(r.outstanding)}{suffix}"
        )
    if len(rows) > max_lines:
        lines.append(f"  • +{len(rows) - max_lines} more")
    return "\n".join(lines)


def collect_notifications(repo: Repo, today: date | None = None) -> list[AppNotification]:
    ref = today or date.today()
    out: list[AppNotification] = []

    low_stock: list[tuple[str, float, float, str]] = []
    for row in repo.list_raw_material_balances():
        rl = row["reorder_level"]
        if rl is None:
            continue
        on_hand = float(row["on_hand"] or 0)
        level = float(rl)
        if on_hand + 1e-9 < level:
            low_stock.append(
                (str(row["short_code"]), on_hand, level, str(row["unit"] or "Kg"))
            )

    if low_stock:
        bullets = "\n".join(
            f"  • {code} — {oh:,.0f} / {rl:,.0f} {unit}"
            for code, oh, rl, unit in low_stock[:8]
        )
        if len(low_stock) > 8:
            bullets += f"\n  • +{len(low_stock) - 8} more"
        n = len(low_stock)
        title = (
            f"Low stock: {low_stock[0][0]}"
            if n == 1
            else f"Low stock: {n} materials"
        )
        out.append(
            AppNotification(
                kind="reorder_low",
                severity="warning",
                title=title,
                detail=bullets,
                nav_action="open_raw_materials",
                action_label="Raw materials",
            )
        )

    due_today_rows = repo.due_rows(
        ref, only_due_today=True, due_from=None, due_to=None
    )
    if due_today_rows:
        n = len(due_today_rows)
        total = sum(r.outstanding for r in due_today_rows)
        out.append(
            AppNotification(
                kind="due_today",
                severity="info",
                title=f"Due today: {n} invoice{'s' if n != 1 else ''}",
                detail=f"{_fmt_inr(total)} total\n{_due_today_lines(due_today_rows)}",
                nav_action="open_due_today",
                action_label="Due today",
            )
        )

    overdue_rows = repo.due_rows(ref, only_overdue=True, due_from=None, due_to=None)
    if overdue_rows:
        n = len(overdue_rows)
        total = sum(r.outstanding for r in overdue_rows)
        out.append(
            AppNotification(
                kind="overdue",
                severity="critical",
                title=f"Overdue: {n} invoice{'s' if n != 1 else ''}",
                detail=f"{_fmt_inr(total)} total\n{_overdue_lines(overdue_rows)}",
                nav_action="open_overdue",
                action_label="Overdue",
            )
        )

    return out
