# Web migration strategy (FastAPI + React)



This is the **planned parallel track** from the README — not a replacement for the desktop app.



## Why build a web app?



| Problem | Web answer |

|---------|------------|

| Owner away from the Windows PC | Check outstanding, overdue, and reminders in a browser |

| Quick payment entry without opening desktop | **Record payment** with the same **FIFO allocation** as PySide6 |

| Portfolio / interviews | Shows full-stack: shared `src/repo`, session auth, React SPA — without duplicating business rules |



**Still desktop-only:** GST Excel invoices, production batches, RM lots, analytics, settings, trash, audit log.



## Principle



| Track | Role |

|--------|------|

| **Desktop (`main`)** | Full product: PySide6 UI, Excel invoices, all screens |

| **Web (`feature/web-api`)** | Companion: monitor + payments (+ owner: add customer) |



Same **SQLite schema** and **`src/repo`** — the API must not fork business rules.



## Phases



### Phase 0 — Done on `main`



- `src/domain.py` + tests for pure logic

- `src/repo/` package (helpers, models, `core.py`)

- `pytest` + GitHub Actions CI

- Owner email digests (`src/email_alerts.py`, `src/notifications.py`)



### Phase 1 — Read-only API + dashboard — done



| Deliverable | Status |

|-------------|--------|

| `api/main.py` FastAPI | Done |

| `GET /api/health`, `/dashboard`, `/due`, `/reminders` | Done |

| `web/` Vite + React | Done |



### Phase 2 — Usable companion — done on `feature/web-api`



| Deliverable | Status |

|-------------|--------|

| Session login (`owner` / `worker`, same DB users as desktop) | Done |

| `POST /api/payments` — FIFO via `repo.create_payment` | Done |

| `GET /api/payments`, `GET/POST /api/customers` (POST owner-only) | Done |

| React: sign-in, record payment, recent list, owner add customer | Done |

| `tests/test_api.py` auth + payment tests | Done |



**Out of scope for Phase 2:** browser invoicing, openpyxl download, trash, production UI.



### Phase 3 — Deploy (optional)



- API on Render/Fly/Railway; React static on Vercel

- Set `PT_WEB_SECRET` in production (session signing)

- **DB:** copy `personalized_tally.db` or sync — Postgres migration is a large separate effort

#### Use from another laptop (no desktop app on that machine)



| Machine | Needs |
|---------|--------|
| **Server** (office PC or cloud) | Repo clone, Python venv, `data/personalized_tally.db`, `uvicorn` running |
| **Client** (any laptop/tablet) | Only a **browser** — no PySide6, no PersonalizedTally install |

The desktop app is **not** required on the client. The API reads/writes the same SQLite file the desktop uses (usually on the server PC).

**Same Wi‑Fi / LAN (quick test):** on the PC that has the DB:

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

On the other laptop, open `http://<server-ip>:8000/docs` to confirm API. For the React UI in dev, run `npm run dev` on the server and open `http://<server-ip>:5173`, or build static files (`cd web && npm run build`) and serve `web/dist` behind the API.

Update CORS in `api/main.py` if the browser origin is not `localhost:5173`. Use a strong `PT_WEB_SECRET` and prefer HTTPS before exposing outside your network.



## What we do **not** do



- Big-bang “migrate desktop to web”

- Duplicate FIFO/COGS logic in React

- Require web for daily ops

- Merge `feature/web-api` to `main` until you explicitly open and approve a PR



## Branch workflow



```text

main              → desktop only; CI unchanged for daily use

feature/web-api   → FastAPI + React; push here; PR when demo-ready

```



## Invoice / Excel on web (future)



Keep **openpyxl on the server** when invoice APIs exist. React downloads `.xlsx` from an endpoint — same templates as desktop.



## ML / full-stack interviews



- **Full-stack:** “Desktop is the system of record; web companion shares `Repo` for payments and receivables monitoring.”

- **ML:** use a separate LLM project; this web slice is optional for ML roles

