/**
 * Authentication API functions.
 *
 * WHAT: Real API calls to M8's /auth/register and /auth/login endpoints.
 *       Previously these were mock localStorage operations (P1/P2).
 *
 * WHY: M8 now has real auth endpoints that hash passwords and generate
 *      API keys. The frontend just needs to call these and store the
 *      returned key as the Bearer token for all subsequent API calls.
 */

import type { UserProfile } from '@/types';

const BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export interface AuthResult {
  user: UserProfile;
  token: string;  // sk-m8-xxx API key for Bearer auth
}

export async function authLogin(
  email: string,
  password: string,
): Promise<AuthResult> {
  const res = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Invalid email or password');
  }

  const data = await res.json();
  return {
    user: {
      user_id: data.user_id,
      username: data.username,
      email: data.email,
      role: data.tier,
    },
    token: data.api_key,
  };
}

export async function authForgotPassword(email: string): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    // Don't reveal whether email exists — 200 even for unknown emails
    if (res.status === 429) throw new Error('Too many attempts. Please wait.');
    if (res.status >= 500) throw new Error('Server error. Please try again.');
  }

  return res.json().catch(() => ({ message: 'If that email is registered, a reset link has been sent.' }));
}

export async function authResetPassword(
  token: string,
  newPassword: string,
): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    if (res.status === 400) throw new Error(err.detail || 'Invalid or expired reset token.');
    if (res.status >= 500) throw new Error('Server error. Please try again.');
  }

  return res.json();
}

export async function authRegister(
  username: string,
  email: string,
  password: string,
): Promise<AuthResult> {
  const res = await fetch(`${BASE_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, email, password, tier: 'basic' }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    if (res.status === 409) {
      throw new Error('Username or email already exists');
    }
    throw new Error(err.detail || 'Registration failed');
  }

  const data = await res.json();
  return {
    user: {
      user_id: data.user_id,
      username: data.username,
      email: data.email,
      role: data.tier,
    },
    token: data.api_key,
  };
}
