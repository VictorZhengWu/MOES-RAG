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
