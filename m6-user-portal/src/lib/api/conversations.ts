/**
 * Conversation CRUD API functions.
 *
 * WHY: Encapsulates all conversation API calls behind typed functions.
 * Components only call listConversations() / getConversation() etc.
 * without worrying about HTTP method, path, or error handling.
 */

import type {
  ConversationListResponse,
  ConversationDetailResponse,
} from '@/types';
import { apiGet, apiDelete, apiPatch } from './client';

export async function listConversations(
  token?: string,
): Promise<ConversationListResponse> {
  return apiGet<ConversationListResponse>('/api/v1/conversations', token);
}

export async function getConversation(
  id: string,
  token?: string,
): Promise<ConversationDetailResponse> {
  return apiGet<ConversationDetailResponse>(
    `/api/v1/conversations/${id}`,
    token,
  );
}

export async function deleteConversation(
  id: string,
  token?: string,
): Promise<{ deleted: boolean }> {
  return apiDelete(`/api/v1/conversations/${id}`, token);
}

export async function renameConversation(
  id: string,
  title: string,
  token?: string,
): Promise<{ conversation_id: string; title: string }> {
  return apiPatch(`/api/v1/conversations/${id}`, { title }, token);
}

export async function shareConversation(
  id: string,
  token?: string,
): Promise<{ share_token: string; share_url: string }> {
  return apiPost<{ share_token: string; share_url: string }>(
    `/api/v1/conversations/${id}/share`, {}, token,
  );
}

export async function pinConversation(
  id: string,
  isPinned: boolean,
  token?: string,
): Promise<{ conversation_id: string; is_pinned: boolean }> {
  return apiPatch(`/api/v1/conversations/${id}/pin`, { is_pinned: isPinned }, token);
}

export async function deleteAccount(
  token?: string,
): Promise<{ deleted: boolean }> {
  // Use fetch directly (not apiDelete) because DELETE /auth/account is a special endpoint
  const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(`${baseUrl}/auth/account`, { method: 'DELETE', headers });
  if (!res.ok) throw new Error(`Delete account failed: ${res.status}`);
  return res.json();
}
