# Web migration strategy (FastAPI + React)

This is the **planned parallel track** from the README — not a replacement for the desktop app.

## Principle

| Track | Role |
|--------|------|
| **Desktop (main)** | Full product: PySide6 UI, Excel invoices, all write paths |
| **Web (branch)** | Portfolio + optional remote read/monitor: FastAPI + React SPA |

Same **SQLite schema** and **`src/repo`** — the API must not fork business rules.

## Phases

### Phase 0 — Done on `main`

- `src/domain.py` + tests for pure logic
- `src/repo/` package (helpers, models, `core.py`)
- `pytest` + GitHub Actions CI
- Owner email digests (`src/email_alerts.py`, `src/notifications.py`)

### Phase 1 — `feature/web-api` (portfolio slice)

**Goal:** Prove full-stack without rewriting the desktop UI.

| Deliverable | Notes |
|-------------|--------|
| `api/` FastAPI app | Lifespan: connect DB, `migrate()`, shared `Repo` |
| Read-only routes | `GET /health`, `/dashboard`, `/due`, `/reminders` |
| `web/` Vite + React | One dashboard page calling the API |
| CORS | Dev: React `:5173` → API `:8000` |
| Docs | README section + run instructions |

**Out of scope for Phase 1:** login parity, creating invoices/payments in browser, openpyxl in browser.

### Phase 2 — Writes behind API (optional)

- `POST /payments`, `POST /customers` with same validation as desktop
- Simple API key or session cookie for owner-only writes
- Desktop remains primary for Excel generation

### Phase 3 — Deploy (optional)

- API on Render/Fly/Railway; React static on Vercel
- **DB:** copy/sync `personalized_tally.db` or migrate to Postgres later (large effort — defer)

## What we do **not** do

- Big-bang “migrate desktop to web”
- Duplicate FIFO/COGS logic in React
- Require web for daily ops

## Branch workflow

```text
main          → desktop releases, stable
feature/web-api → FastAPI + React only; merge when demo-ready
```

## Invoice / Excel on web

Keep **openpyxl on the server** when write APIs exist (Phase 2+). The React app downloads `.xlsx` from an API endpoint — same templates as desktop.

## ML / full-stack interviews

- **Full-stack:** demo Phase 1 in browser + link to desktop repo
- **ML:** use a separate LLM project; this web slice is optional for ML roles
