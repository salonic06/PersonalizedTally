# Portfolio pack (SDE1 · full-stack)

## Elevator pitch (30 seconds)

I built an **offline desktop operations app** for Indian SMBs — GST-style Excel invoices, receivables, **FIFO payment allocation**, inventory and production costing — plus a **FastAPI + React companion** that reuses the same `Repo` layer so business rules live in one place. It has **pytest**, **GitHub Actions**, role-based auth, and owner email digests.

## Tech stack (put on resume / GitHub About)

| Layer | Technologies |
|--------|----------------|
| Desktop UI | Python 3.12, PySide6 |
| Web companion | FastAPI, React, TypeScript, Vite (`feature/web-api`) |
| Data | SQLite (WAL, FKs, migrations, SQL views) |
| Integrations | openpyxl (invoices), SMTP (owner digests) |
| Quality | pytest (40+ tests), GitHub Actions (Windows) |

**GitHub topics:** `python`, `sqlite`, `pyside6`, `fastapi`, `react`, `pytest`, `fullstack`

## Resume bullets (copy-paste)

- Built **PySide6 + SQLite** desktop app for invoicing, AR, inventory, and production with **FIFO payment allocation** and **batch COGS** on invoice lines.
- Refactored data layer into **`src/repo`** package; added **pytest** (FIFO, COGS, ledger, notifications, API auth) and **GitHub Actions** CI on Windows.
- Shipped **FastAPI + React** companion (`feature/web-api`): session auth, receivables dashboard, **record payments** via shared `Repo` — no duplicated domain logic in the frontend.
- Implemented **openpyxl** invoice generation, receivables aging, audit log, role-based access, and **owner email digests** (SMTP).

## What impresses SDE1 interviewers

| Signal | Evidence in this repo |
|--------|------------------------|
| Domain logic | FIFO, due dates, aging buckets, COGS |
| Data design | Migrations, views, soft delete, audit log |
| Testing | Unit tests on money paths, API tests |
| Layering | `ui` / `api` / `repo` / `domain` / `db` |
| Full-stack | Desktop + API + SPA, shared schema |
| Pragmatism | Desktop = full product; web = companion |

## GitHub checklist

- [x] Architecture diagram + legend in README
- [x] `docs/DEMO.md` — walkthrough script
- [ ] **2–3 PNGs** in `docs/screenshots/` (desktop)
- [ ] **1 PNG** web payment screen (optional)
- [ ] **Loom 60–90s** — link in README
- [ ] Pin repo; strong description; topics above
- [ ] PR `feature/web-api` → `main` when ready (or link branch in README)

## ML roles

This repo is **not** ML. Pair on your profile with an LLM/RAG project. Optional tie-in: export analytics CSV → notebook (only if you actually build it).

## UI polish (optional, before screenshots)

See [UI_ROADMAP.md](UI_ROADMAP.md) Phase 1 — primary buttons, nav labels. Do **before** Loom if you want a sharper visual.

## Branch map

| Branch | What reviewers see |
|--------|---------------------|
| `main` | Desktop product, CI, tests, email digests |
| `feature/web-api` | Everything in `main` + FastAPI + React companion |

**Web branch:** clone → `feature/web-api` → follow [DEMO.md](DEMO.md).
