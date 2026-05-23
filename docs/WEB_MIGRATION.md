# Web companion (FastAPI + React)

The **desktop app stays the full product**. The web layer is an optional companion: monitor receivables and record payments in a browser using the same SQLite database and `src/repo` rules (including FIFO allocation).

**Desktop-only:** GST Excel invoices, production, raw materials UI, analytics, settings, trash, audit log.

## Layout

| Path | Role |
|------|------|
| `api/` | FastAPI — session auth, dashboard, due, reminders, payments, customers |
| `web/` | React SPA (Vite) |
| `requirements-api.txt` | fastapi, uvicorn, pydantic, itsdangerous |

## Run locally

**One port (built UI + API):**

```powershell
.\tools\run_web_demo.ps1
```

→ http://localhost:8000

**Development (hot reload):**

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --reload --port 8000
cd web && npm install && npm run dev
```

→ UI http://localhost:5173 · API http://127.0.0.1:8000/docs

## LAN / another device

On the PC that holds `data/personalized_tally.db`:

1. `uvicorn api.main:app --host 0.0.0.0 --port 8000`
2. `cd web && npm run dev` (or use `run_web_demo.ps1` on port 8000 only)
3. Other device: `http://<server-ip>:5173` or `:8000`

Use `tools/check_lan.ps1` and, if needed, `tools/open_lan_firewall.ps1` (Administrator). Prefer **Private** Wi‑Fi profile on Windows, or a shared phone hotspot if the router blocks device-to-device traffic.

## Deploy (optional)

Host API + `personalized_tally.db` on a small VM or PaaS with a persistent disk; serve `web/dist` from the API (`PT_SERVE_WEB=1`) or a static host. Set `PT_WEB_SECRET` for session signing. Full multi-device sync is out of scope today — copy the DB when desktop and server diverge.

## Tests

`tests/test_api.py` — auth, dashboard, payments, due filters (uses isolated temp DB).
