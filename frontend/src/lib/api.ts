export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export type AuthResponse = {
  access_token: string;
  token_type: string;
  org_id: string;
};

export type InvoiceStatus = "uploaded" | "processing" | "review" | "completed" | "failed";

export type Invoice = {
  id: string;
  org_id: string;
  filename: string;
  status: InvoiceStatus;
  currency: string | null;
  total: string | null;
  supplier_name: string | null;
  created_at: string;
};

export type SessionStatus = "draft" | "active" | "processing" | "completed" | "archived";

export type Session = {
  id: string;
  org_id: string;
  name: string;
  description: string | null;
  status: SessionStatus;
  requested_fields: Array<{ name: string; type: string; description: string }>;
  result_count: number;
  created_at: string;
  updated_at: string;
};

export type ExtractionField = {
  field_name: string;
  field_value: Record<string, unknown> | null;
  confidence: number | null;
  page: number | null;
  source_text: string | null;
  validation_status: string | null;
};

export type SearchQuery = {
  query: string;
  org_id: string;
};

export type SearchResult = {
  field_name: string;
  field_value: Record<string, unknown> | null;
  confidence: number | null;
  source_text: string | null;
  validation_status: string | null;
};

const TOKEN_KEY = "invoiceiq_access_token";
const ORG_KEY = "invoiceiq_org_id";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export function isUnauthorized(err: unknown): boolean {
  return err instanceof ApiError && err.status === 401;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setSession(auth: AuthResponse): void {
  window.localStorage.setItem(TOKEN_KEY, auth.access_token);
  window.localStorage.setItem(ORG_KEY, auth.org_id);
}

export function getOrgId(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ORG_KEY);
}

export function clearSession(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(ORG_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    clearSession();
    throw new ApiError("Not authenticated", 401);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const detail = body?.detail ?? `Request failed (${res.status})`;
    throw new ApiError(typeof detail === "string" ? detail : JSON.stringify(detail), res.status);
  }
  return (await res.json()) as T;
}

export function register(payload: {
  email: string;
  password: string;
  full_name: string;
  org_name: string;
}): Promise<AuthResponse> {
  return request("/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function login(payload: { email: string; password: string }): Promise<AuthResponse> {
  const tokens = await request<{ access_token: string; refresh_token: string }>("/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  window.localStorage.setItem(TOKEN_KEY, tokens.access_token);
  const me = await request<{ org_id: string }>("/v1/auth/me");
  return { access_token: tokens.access_token, token_type: "bearer", org_id: me.org_id };
}

export function listInvoices(orgId: string): Promise<Invoice[]> {
  return request(`/v1/orgs/${orgId}/invoices`);
}

export function uploadInvoice(file: File): Promise<Invoice[]> {
  const form = new FormData();
  form.append("files", file);
  return request("/v1/invoices", { method: "POST", body: form });
}

export function listSessions(orgId: string): Promise<Session[]> {
  return request(`/v1/sessions?org_id=${orgId}`);
}

export function createSession(payload: {
  name: string;
  description?: string;
  requested_fields: Array<{ name: string; type?: string; description?: string }>;
}): Promise<Session> {
  return request("/v1/sessions", { method: "POST", body: JSON.stringify(payload) });
}

export function getSession(sessionId: string): Promise<Session> {
  return request(`/v1/sessions/${sessionId}`);
}

export function rerunSession(sessionId: string): Promise<Session> {
  return request(`/v1/sessions/${sessionId}/rerun`, { method: "POST" });
}

export function uploadToSession(sessionId: string, file: File): Promise<Invoice[]> {
  const form = new FormData();
  form.append("files", file);
  return request(`/v1/sessions/${sessionId}/upload`, { method: "POST", body: form });
}

export function getExtractionResults(sessionId: string): Promise<ExtractionField[]> {
  return request(`/v1/sessions/${sessionId}/results`);
}

export function searchExtractions(query: SearchQuery): Promise<SearchResult[]> {
  return request("/v1/search", { method: "POST", body: JSON.stringify(query) });
}

export function exportResults(sessionId: string, format: string, config?: Record<string, unknown>): Promise<{ id: string; status: string }> {
  return request(`/v1/sessions/${sessionId}/export`, { method: "POST", body: JSON.stringify({ format, ...config }) });
}
