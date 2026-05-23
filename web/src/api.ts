const API = "/api";

export type User = { username: string; role: string };

export type Dashboard = {
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

export type DueRow = {
  invoice_id: number;
  invoice_no: string;
  customer_name: string;
  due_date: string;
  outstanding: number;
  days_overdue: number;
};

export type Reminder = {
  kind: string;
  severity: string;
  title: string;
  detail: string;
};

export type Customer = { id: number; name: string; credit_days: number };

export type Payment = {
  id: number;
  customer_id: number;
  customer_name: string;
  payment_date: string;
  amount: number;
  mode: string;
  reference: string;
};

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (res.status === 401) {
    throw new Error("UNAUTHORIZED");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = (await res.json()) as { detail?: string };
      if (typeof j.detail === "string") detail = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const client = {
  me: () => api<User>("/auth/me"),
  login: (username: string, password: string) =>
    api<User>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => api<{ status: string }>("/auth/logout", { method: "POST" }),
  dashboard: () => api<Dashboard>("/dashboard"),
  reminders: () => api<{ items: Reminder[] }>("/reminders"),
  due: (params: { overdue?: boolean; due_today?: boolean }) => {
    const q = new URLSearchParams();
    if (params.overdue) q.set("overdue", "true");
    if (params.due_today) q.set("due_today", "true");
    if (!params.overdue && !params.due_today) {
      q.set("overdue", "false");
      q.set("due_today", "false");
    }
    return api<DueRow[]>(`/due?${q}`);
  },
  customers: () => api<Customer[]>("/customers"),
  createCustomer: (name: string, credit_days: number) =>
    api<Customer>("/customers", {
      method: "POST",
      body: JSON.stringify({ name, credit_days }),
    }),
  payments: () => api<Payment[]>("/payments?limit=30"),
  createPayment: (body: {
    customer_id: number;
    payment_date: string;
    amount: number;
    mode: string;
    reference: string;
  }) =>
    api<{ id: number; message: string }>("/payments", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

export function inr(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}
