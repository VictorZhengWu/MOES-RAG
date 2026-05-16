import type { LLMBackend } from '@/types';
import { apiGet, apiPost, apiDelete } from './client';

export async function listBackends(): Promise<{ backends: LLMBackend[]; total: number }> {
  return apiGet('/api/v1/admin/llm/backends');
}

export async function createBackend(data: Partial<LLMBackend>): Promise<LLMBackend> {
  return apiPost('/api/v1/admin/llm/backends', data);
}

export async function updateBackend(id: string, data: Partial<LLMBackend>): Promise<{ updated: boolean }> {
  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000'}/api/v1/admin/llm/backends/${id}`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Update failed: ${res.status}`);
  return res.json();
}

export async function deleteBackend(id: string): Promise<{ deleted: boolean }> {
  return apiDelete(`/api/v1/admin/llm/backends/${id}`);
}
