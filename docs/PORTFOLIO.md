# Portfolio angles (SDE · full-stack · ML)

Use this when tailoring your resume and GitHub profile.

## One-line pitch

Desktop operations app for Indian SMBs: GST invoices, AR with **FIFO payments**, inventory + production costing, analytics, pytest + CI, owner email digests.

## By role type

### SDE (general / backend-leaning)

Lead with: **domain logic** (FIFO, COGS, `invoice_balances` view), **data integrity** (FKs, soft delete, migrations), **tests + CI**, audit log.

Interview stories: payment allocation order; trashed payment vs outstanding; batch yield → cost/kg.

### Full-stack

Same as SDE, plus: clear **layering** (`ui` / `repo` / `db` / `domain`), headless **openpyxl** invoice generation.

Stretch project (separate PR): **FastAPI** read-only API + small **React** dashboard for due/outstanding — reuses SQLite schema; 1–2 weekends.

### ML / AI

This repo is **not** an ML project. Pair it on your profile with **Mental Wellness Chatbot** (or similar): LLM, RAG, API.

Optional light ML tie-in here (only if you build it): export analytics CSV → notebook for sales forecast; or “anomaly” flag on overdue spikes — do not fake ML in the desktop app without real models.

## Resume bullets (template)

- Built **PySide6 + SQLite** desktop app for invoicing, AR, and inventory with **FIFO payment allocation** and production **batch COGS** on invoice lines.
- Implemented **openpyxl** invoice generation, receivables aging, role-based auth, audit log, and **owner email digests** (SMTP).
- Added **pytest** suite (FIFO, COGS, ledger, trash/restore) and **GitHub Actions** CI on Windows.

## GitHub checklist

- [ ] Architecture diagram in README (below)
- [ ] 2–3 screenshots in `docs/screenshots/` linked from README
- [ ] Optional Loom link in README
- [ ] Pinned repo with clear description and topics: `python`, `sqlite`, `pyside6`, `pytest`

## UI / design (next pass)

See [UI_ROADMAP.md](UI_ROADMAP.md) — nav grouping, primary actions, optional dark mode. Not required for backend interviews; helps product/full-stack screens.
