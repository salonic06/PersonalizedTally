# Demo walkthrough

**Goal:** Show one coherent product in **3–5 minutes** — domain depth, tests/CI, and the web companion.

## Setup (15 min)

```powershell
git clone https://github.com/salonic06/PersonalizedTally.git
cd PersonalizedTally
git checkout feature/web-api
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt -r requirements-api.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe tools\seed_demo.py --yes
```

Add **2–3 screenshots** to `docs/screenshots/` (see that folder). Optional **60s Loom** — script below.

## Story arc

1. **Problem** — SMB needs dues, payments, GST invoices without heavy ERP training.
2. **Architecture** — PySide6 UI → `src/repo` → SQLite; web companion reuses **same repo** (no duplicated FIFO).
3. **Hard part** — **FIFO payment allocation**; production **batch COGS** on invoice lines.
4. **Quality** — migrations, soft delete + trash, audit log, **41+ pytest**, GitHub Actions on Windows.
5. **Full-stack** — FastAPI session auth + React: monitor AR, record payment from browser.

## Desktop (2–3 min)

| Step | Screen | Point to make |
|------|--------|----------------|
| 1 | Login `owner` | Role-based nav (worker vs owner) |
| 2 | Dashboard | Outstanding, MTD, reminders banner |
| 3 | Due / Outstanding | Filters; overdue list |
| 4 | Payments | Save payment → **auto FIFO** |
| 5 | Customer Ledger | Running balance after payment |
| 6 | (Optional) Production / RM | COGS path if time |

```powershell
.\.venv\Scripts\python.exe app.py
```

## Web companion (1–2 min)

```powershell
.\tools\run_web_demo.ps1
```

Open http://localhost:8000 → sign in → record a payment → show due list updates.

## Loom script (~60 seconds)

1. “Desktop-first ops for a small business.”
2. Dashboard + Reminders (10s).
3. Due overdue → Payments → FIFO save (20s).
4. Browser login + payment on same DB (20s).
5. “Tests cover FIFO, COGS, API auth — CI on GitHub.” (10s).

## Common questions (code map)

| Question | Where |
|----------|--------|
| FIFO allocation? | `src/repo/core.py` — `allocate_payment_fifo`, `create_payment` |
| Outstanding? | SQL view `invoice_balances` + `due_rows` |
| Why SQLite? | Single-file desktop; web reads same DB |
| No duplicate rules in React? | Thin UI; writes via API → `Repo` |
| Security? | Password hash + pepper; session cookie; owner-only customer POST |

## Out of scope

GSTR filing, multi-user sync. ML belongs in a separate project.

## Deploy (optional live URL)

See [WEB_MIGRATION.md](WEB_MIGRATION.md) — Render/Fly + `PT_WEB_SECRET` + DB copy.
