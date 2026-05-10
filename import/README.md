# Import folder (bulk invoice seed)

Use **Setup → Seed Data → Import invoices from folder** and pick a directory that contains **GST-style invoice `.xlsx`** files matching your app template (same layout as `assets/invoice_template.xlsx`).

**For this public repository:** do not commit real customer files. Only documentation lives here; `*.xlsx` / `*.pdf` under `import/` are ignored by `.gitignore`.

**Dummy business data:** run from the repo root:

```powershell
python tools/seed_demo.py --yes
python app.py
```

That wipes the local DB and loads **fictional** customers, invoices, payments, RM, and production — including invoice files under `invoices/<FY>/`, not under `import/`.

To try bulk import locally, copy a few **synthetic** workbooks into `import/sample/` on your machine (they are not tracked in git).
