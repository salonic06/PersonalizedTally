# UI / design roadmap (next)

Current: Fusion + light blue-gray theme (`src/ui/theme.py`), large nav, readable tables.

## Phase 1 — Quick polish — done

- Primary button style for **Save**, **Send email now**, **Save Payment**, **Generate invoice**, **Add Payment** (header)
- Nav icons for Dashboard, Invoices, Due, Ledger, Payments (`src/ui/theme.py`, `main_window.py`)
- Page title + subtitle on every screen (`src/ui/page_header.py`)

## Phase 2 — Information hierarchy (2–3 days)

- Group nav: **Sales** (Invoices, Due, Aging, Ledger) · **Stock** (RM, Production) · **Admin** (Analytics, Audit, Trash, Setup, Settings)
- Dashboard cards: color only for “needs attention” (overdue, low stock)
- Empty states (“No overdue invoices”) instead of blank tables

## Phase 3 — Optional

- Dark mode toggle in Settings
- Keyboard shortcuts (Ctrl+F focus search, Ctrl+1…9 nav)

Do Phase 1 before recording screenshots/Loom so the repo looks finished on camera.
