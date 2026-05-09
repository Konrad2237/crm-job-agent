export type Company = {
  id: string;
  name: string;
  url: string;
  domain: string;
  what_they_do: string | null;
  source: string;
  status: string;
  position: string | null;
  salary_expectation: string | null;
  contact_email: string | null;
  notes: string | null;
  reply_received: string | null;
  reply_status: string | null;
  created_at: string;
  applied_at: string | null;
  updated_at: string;
};

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const API_SECRET = process.env.NEXT_PUBLIC_API_SECRET;

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (API_SECRET) headers["X-Api-Key"] = API_SECRET;

  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...headers, ...(init?.headers as Record<string, string> | undefined) },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail?.message ?? body?.detail ?? `HTTP ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  findCompany: () => apiFetch<Company>("/find", { method: "POST" }),

  skipCompany: (id: string) =>
    apiFetch<Company>(`/companies/${id}/skip`, { method: "POST" }),

  applyCompany: (
    id: string,
    data: { position?: string; salary_expectation?: string; contact_email?: string; notes?: string }
  ) =>
    apiFetch<Company>(`/companies/${id}/apply`, {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getCompanies: (params: { page?: number; limit?: number; status?: string }) => {
    const q = new URLSearchParams();
    if (params.page) q.set("page", String(params.page));
    if (params.limit) q.set("limit", String(params.limit));
    if (params.status) q.set("status", params.status);
    return apiFetch<Company[]>(`/companies?${q}`);
  },

  deleteCompany: (id: string) =>
    apiFetch<void>(`/companies/${id}`, { method: "DELETE" }),

  patchCompany: (
    id: string,
    data: {
      reply_status?: string | null;
      reply_received?: string | null;
      status?: string;
      position?: string;
      notes?: string;
    }
  ) =>
    apiFetch<Company>(`/companies/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  addManualCompany: (data: {
    name: string;
    url: string;
    what_they_do?: string;
    position?: string;
    salary_expectation?: string;
    contact_email?: string;
    notes?: string;
  }) =>
    apiFetch<Company>("/companies/manual", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};
