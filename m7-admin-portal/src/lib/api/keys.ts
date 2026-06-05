/**
 * API Key management API functions.
 *
 * WHAT: Functions to call M8's /admin/keys endpoints for API key lifecycle
 *       management (create, list, revoke). All calls use the authenticated
 *       API client which sends Bearer tokens to M8 on port 8000.
 *
 * WHY: M7 admin portal needs to manage API keys for users — previously
 *      this was a placeholder. M8 provides these endpoints with proper
 *      authentication and key hash storage.
 */

import { apiGet, apiPost, apiDelete } from './client';

export interface APIKeyInfo {
  key_prefix: string;
  user_id: string;
  tier: string;
  created_at: number;
  is_active: boolean;
  last_used_at: number | null;
}

export interface CreateKeyResponse {
  key: string;        // Full raw key — shown ONCE
  prefix: string;     // "sk-m8-xxxx"
  tier: string;
}

export async function listAPIKeys(userId?: string): Promise<APIKeyInfo[]> {
  const params = userId ? `?user_id=${encodeURIComponent(userId)}` : '';
  return apiGet<APIKeyInfo[]>(`/admin/keys${params}`);
}

export async function createAPIKey(
  userId: string,
  tier: string,
): Promise<CreateKeyResponse> {
  return apiPost<CreateKeyResponse>('/admin/keys', {
    user_id: userId,
    tier,
  });
}

export async function revokeAPIKey(
  keyPrefix: string,
): Promise<{ status: string; key_prefix: string }> {
  return apiDelete(`/admin/keys/${keyPrefix}`);
}
