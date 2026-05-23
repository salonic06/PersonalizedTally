import { useCallback, useEffect, useState } from "react";
import {
  client,
  inr,
  type Customer,
  type Dashboard,
  type DueRow,
  type Payment,
  type Reminder,
  type User,
} from "./api";

function InstallHint() {
  const [install, setInstall] = useState<{ prompt: () => Promise<void> } | null>(null);

  useEffect(() => {
    const onBip = (e: Event) => {
      e.preventDefault();
      const ev = e as Event & { prompt: () => Promise<{ outcome: string }> };
      setInstall({
        prompt: async () => {
          await ev.prompt();
          setInstall(null);
        },
      });
    };
    window.addEventListener("beforeinstallprompt", onBip);
    return () => window.removeEventListener("beforeinstallprompt", onBip);
  }, []);

  if (!install) return null;
  return (
    <p className="install-hint">
      <button type="button" className="secondary" onClick={() => install.prompt()}>
        Install app on this device
      </button>
    </p>
  );
}

function LoginScreen({ onLoggedIn }: { onLoggedIn: (u: User) => void }) {
  const [username, setUsername] = useState("owner");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await client.login(username, password);
      onLoggedIn(u);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="login">
      <h1>Personalized Tally</h1>
      <p className="sub">
        Web companion — monitor receivables and record payments (same FIFO rules as desktop).
        Invoicing and Excel stay in the Windows app.
      </p>
      <InstallHint />
      <form className="panel" onSubmit={submit}>
        <label>
          Username
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}

function DashboardApp({ user, onLogout }: { user: User; onLogout: () => void }) {
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [due, setDue] = useState<DueRow[]>([]);
  const [dueMode, setDueMode] = useState<"overdue" | "due_today">("overdue");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);

  const [payCustomerId, setPayCustomerId] = useState("");
  const [payDate, setPayDate] = useState(new Date().toISOString().slice(0, 10));
  const [payAmount, setPayAmount] = useState("");
  const [payMode, setPayMode] = useState("Bank");
  const [payRef, setPayRef] = useState("");

  const [newCustName, setNewCustName] = useState("");
  const [newCustDays, setNewCustDays] = useState("45");

  const load = useCallback(async () => {
    setError(null);
    try {
      const [d, r, c, p] = await Promise.all([
        client.dashboard(),
        client.reminders(),
        client.customers(),
        client.payments(),
      ]);
      setDash(d);
      setReminders(r.items);
      setCustomers(c);
      setPayments(p);
      if (!payCustomerId && c.length > 0) setPayCustomerId(String(c[0].id));
    } catch (e) {
      if (e instanceof Error && e.message === "UNAUTHORIZED") onLogout();
      else setError(e instanceof Error ? e.message : String(e));
    }
  }, [onLogout, payCustomerId]);

  const loadDue = useCallback(async () => {
    try {
      const rows = await client.due(
        dueMode === "overdue" ? { overdue: true } : { due_today: true },
      );
      setDue(rows);
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

  const savePayment = async (e: React.FormEvent) => {
    e.preventDefault();
    setOk(null);
    setError(null);
    const amount = parseFloat(payAmount);
    if (!payCustomerId || !amount || amount <= 0) {
      setError("Pick a customer and enter a positive amount.");
      return;
    }
    try {
      const res = await client.createPayment({
        customer_id: Number(payCustomerId),
        payment_date: payDate,
        amount,
        mode: payMode,
        reference: payRef,
      });
      setOk(res.message);
      setPayAmount("");
      setPayRef("");
      await load();
      await loadDue();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const addCustomer = async (e: React.FormEvent) => {
    e.preventDefault();
    setOk(null);
    setError(null);
    try {
      const c = await client.createCustomer(newCustName.trim(), Number(newCustDays) || 45);
      setNewCustName("");
      setOk(`Customer “${c.name}” saved.`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const logout = async () => {
    try {
      await client.logout();
    } finally {
      onLogout();
    }
  };

  return (
    <main>
      <InstallHint />
      <header className="topbar">
        <div>
          <h1>Personalized Tally</h1>
          <p className="sub">
            Signed in as <strong>{user.username}</strong> ({user.role}) — payments use desktop FIFO allocation
          </p>
        </div>
        <button type="button" className="secondary" onClick={logout}>
          Sign out
        </button>
      </header>

      {error && <p className="error">{error}</p>}
      {ok && <p className="ok">{ok}</p>}

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
            <label>MTD collections</label>
            <strong>{inr(dash.mtd_collections)}</strong>
          </div>
        </div>
      )}

      <section className="panel">
        <h2>Record payment</h2>
        <form className="form-grid" onSubmit={savePayment}>
          <label>
            Customer
            <select value={payCustomerId} onChange={(e) => setPayCustomerId(e.target.value)} required>
              {customers.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Date
            <input type="date" value={payDate} onChange={(e) => setPayDate(e.target.value)} required />
          </label>
          <label>
            Amount
            <input
              type="number"
              min="0"
              step="0.01"
              value={payAmount}
              onChange={(e) => setPayAmount(e.target.value)}
              placeholder="e.g. 15000"
              required
            />
          </label>
          <label>
            Mode
            <select value={payMode} onChange={(e) => setPayMode(e.target.value)}>
              {["Bank", "UPI", "Cash", "Cheque", "Other"].map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label className="wide">
            Reference
            <input value={payRef} onChange={(e) => setPayRef(e.target.value)} placeholder="UTR / cheque no." />
          </label>
          <div className="wide">
            <button type="submit">Save payment (FIFO allocate)</button>
          </div>
        </form>
      </section>

      {user.role === "owner" && (
        <section className="panel">
          <h2>Add customer</h2>
          <form className="form-grid" onSubmit={addCustomer}>
            <label>
              Name
              <input value={newCustName} onChange={(e) => setNewCustName(e.target.value)} required />
            </label>
            <label>
              Credit days
              <input
                type="number"
                min="1"
                value={newCustDays}
                onChange={(e) => setNewCustDays(e.target.value)}
              />
            </label>
            <div>
              <button type="submit">Save customer</button>
            </div>
          </form>
        </section>
      )}

      <section>
        <h2>Recent payments</h2>
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Customer</th>
              <th className="num">Amount</th>
              <th>Mode</th>
              <th>Reference</th>
            </tr>
          </thead>
          <tbody>
            {payments.map((p) => (
              <tr key={p.id}>
                <td>{p.payment_date}</td>
                <td>{p.customer_name}</td>
                <td className="num">{inr(p.amount)}</td>
                <td>{p.mode || "—"}</td>
                <td>{p.reference || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

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

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    client
      .me()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setChecking(false));
  }, []);

  if (checking) return <main className="login"><p className="sub">Loading…</p></main>;
  if (!user) return <LoginScreen onLoggedIn={setUser} />;
  return <DashboardApp user={user} onLogout={() => setUser(null)} />;
}
