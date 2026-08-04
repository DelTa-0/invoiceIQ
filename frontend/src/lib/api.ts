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
  window.localStorage.removeItem(TOKEN_KEY);
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
