import { useCallback, useEffect, useState } from "react";

type Dashboard = {
  as_of: string;
  total_outstanding: number;
  due_today_count: number;
  overdue_count: number;
  mtd_sales_ex_gst: number;
  mtd_collections: number;
  mtd_gross_profit: number;
  customer_count: number;
  invoice_count: number;
};

type DueRow = {
  invoice_id: number;
  invoice_no: string;
  customer_name: string;
  due_date: string;
  outstanding: number;
  days_overdue: number;
};

type Reminder = {
  kind: string;
  severity: string;
  title: string;
  detail: string;
};

const API = "/api";

function inr(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

export default function App() {
  const [error, setError] = useState<string | null>(null);
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [due, setDue] = useState<DueRow[]>([]);
  const [dueMode, setDueMode] = useState<"overdue" | "due_today" | "all">("overdue");

  const load = useCallback(async () => {
    setError(null);
    try {
      const [dRes, rRes] = await Promise.all([
        fetch(`${API}/dashboard`),
        fetch(`${API}/reminders`),
      ]);
      if (!dRes.ok || !rRes.ok) throw new Error("API request failed — is uvicorn running on :8000?");
      const d = (await dRes.json()) as Dashboard;
      const r = (await rRes.json()) as { items: Reminder[] };
      setDash(d);
      setReminders(r.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  const loadDue = useCallback(async () => {
    try {
      let url = `${API}/due?`;
      if (dueMode === "overdue") url += "overdue=true";
      else if (dueMode === "due_today") url += "due_today=true";
      else url += "overdue=false&due_today=false";
      const res = await fetch(url);
      if (!res.ok) throw new Error("Failed to load due list");
      setDue((await res.json()) as DueRow[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [dueMode]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadDue();
  }, [loadDue]);

  return (
    <main>
      <h1>Personalized Tally</h1>
      <p className="sub">
        Web dashboard (read-only) — same data as the desktop app. Full invoicing stays in PySide6.
      </p>

      {error && <p className="error">{error}</p>}

      {dash && (
        <div className="cards">
          <div className="card">
            <label>Outstanding</label>
            <strong>{inr(dash.total_outstanding)}</strong>
          </div>
          <div className="card">
            <label>Due today</label>
            <strong>{dash.due_today_count}</strong>
          </div>
          <div className="card">
            <label>Overdue</label>
            <strong>{dash.overdue_count}</strong>
          </div>
          <div className="card">
            <label>MTD sales (ex-GST)</label>
            <strong>{inr(dash.mtd_sales_ex_gst)}</strong>
          </div>
          <div className="card">
            <label>MTD collections</label>
            <strong>{inr(dash.mtd_collections)}</strong>
          </div>
          <div className="card">
            <label>MTD gross profit</label>
            <strong>{inr(dash.mtd_gross_profit)}</strong>
          </div>
        </div>
      )}

      <section>
        <h2>Reminders</h2>
        {reminders.length === 0 && <p>Nothing to act on today.</p>}
        {reminders.map((r, i) => (
          <div key={i} className={`reminder ${r.severity}`}>
            <strong>{r.title}</strong>
            <pre>{r.detail}</pre>
          </div>
        ))}
      </section>

      <section>
        <h2>Due / outstanding</h2>
        <div className="tabs">
          <button
            type="button"
            className={dueMode === "overdue" ? "active" : ""}
            onClick={() => setDueMode("overdue")}
          >
            Overdue
          </button>
          <button
            type="button"
            className={dueMode === "due_today" ? "active" : ""}
            onClick={() => setDueMode("due_today")}
          >
            Due today
          </button>
        </div>
        <table>
          <thead>
            <tr>
              <th>Invoice</th>
              <th>Customer</th>
              <th>Due date</th>
              <th className="num">Outstanding</th>
              <th className="num">Days</th>
            </tr>
          </thead>
          <tbody>
            {due.map((row) => (
              <tr key={row.invoice_id}>
                <td>{row.invoice_no}</td>
                <td>{row.customer_name}</td>
                <td>{row.due_date}</td>
                <td className="num">{inr(row.outstanding)}</td>
                <td className="num">{row.days_overdue}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}
