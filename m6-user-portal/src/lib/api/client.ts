/**
 * HTTP client wrapper for the Marine & Offshore Expert System API.
 *
 * WHY: Centralizing API base URL, auth headers, and error handling
 * in one place avoids duplication across chat.ts, conversations.ts,
 * etc. When switching from Mock Server to real M5, only the
 * BASE_URL constant changes — all API functions stay the same.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function buildHeaders(token?: string): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
    // Also send API key as X-API-Key header (some API gateways prefer this)
    headers['X-API-Key'] = token;
  }
  return headers;
}

async function handleResponse(res: Response): Promise<unknown> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      res.status,
      body.detail || body.error || res.statusText,
      body.code,
    );
  }
  return res.json();
}

export async function apiGet<T>(path: string, token?: string): Promise<T> {
  const headers = await buildHeaders(token);
  const res = await fetch(`${BASE_URL}${path}`, { headers });
  return handleResponse(res) as Promise<T>;
}

export async function apiPost<T>(
  path: string,
  body: unknown,
  token?: string,
): Promise<T> {
  const headers = await buildHeaders(token);
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  return handleResponse(res) as Promise<T>;
}

export async function apiDelete<T>(
  path: string,
  token?: string,
): Promise<T> {
  const headers = await buildHeaders(token);
  const res = await fetch(`${BASE_URL}${path}`, { method: 'DELETE', headers });
  return handleResponse(res) as Promise<T>;
}

export async function apiPatch<T>(
  path: string,
  body: unknown,
  token?: string,
): Promise<T> {
  const headers = await buildHeaders(token);
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify(body),
  });
  return handleResponse(res) as Promise<T>;
}
