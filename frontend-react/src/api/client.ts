// Thin fetch wrapper around the FastAPI backend. Mirrors the Streamlit
// frontend's _get_json/_auth_headers/_error_detail helpers — same backend,
// same conventions, just a browser fetch() instead of Python requests.

export const BACKEND_URL: string =
  (import.meta.env.VITE_BACKEND_URL as string | undefined) ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let authToken: string | null = null;

/** Called by AuthContext on login/logout/restore-from-storage. */
export function setAuthToken(token: string | null): void {
  authToken = token;
}

function authHeaders(): HeadersInit {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

/** Best-effort human-readable error message from a failed response — same
 * fallback chain as the Streamlit frontend's _error_detail(). */
async function errorDetail(resp: Response): Promise<string> {
  try {
    const body = (await resp.json()) as { detail?: string };
    if (body && typeof body.detail === "string") return body.detail;
  } catch {
    // not JSON — fall through to raw text
  }
  try {
    return await resp.text();
  } catch {
    return `HTTP ${resp.status}`;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
  opts: { auth?: boolean } = {}
): Promise<T> {
  const useAuth = opts.auth !== false;
  const headers: HeadersInit = {
    ...(useAuth ? authHeaders() : {}),
    ...(init.headers ?? {}),
  };
  let resp: Response;
  try {
    resp = await fetch(`${BACKEND_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Backend not reachable. Is it running?");
  }
  if (!resp.ok) {
    throw new ApiError(resp.status, await errorDetail(resp));
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export function apiGet<T>(path: string, opts?: { auth?: boolean }): Promise<T> {
  return request<T>(path, { method: "GET" }, opts);
}

export function apiPost<T>(path: string, body?: unknown, opts?: { auth?: boolean }): Promise<T> {
  return request<T>(
    path,
    {
      method: "POST",
      headers: body !== undefined ? { "Content-Type": "application/json" } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    },
    opts
  );
}

export function apiDelete<T>(path: string, opts?: { auth?: boolean }): Promise<T> {
  return request<T>(path, { method: "DELETE" }, opts);
}

/** Multipart upload — used for /upload. */
export function apiUploadFile<T>(path: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  return request<T>(path, { method: "POST", body: form });
}
