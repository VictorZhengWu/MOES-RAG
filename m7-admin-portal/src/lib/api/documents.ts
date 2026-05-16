import type { DocumentRecord, ParseTask } from '@/types';
import { apiGet, apiPost, apiDelete } from './client';

export async function listDocuments(): Promise<{ documents: DocumentRecord[]; total: number }> {
  return apiGet('/api/v1/admin/documents');
}

export async function uploadDocument(metadata: Record<string, unknown>): Promise<{ task_id: string; doc_id: string; status: string }> {
  return apiPost('/api/v1/admin/documents/upload', metadata);
}

export async function getParseStatus(taskId: string): Promise<ParseTask> {
  return apiGet(`/api/v1/admin/documents/${taskId}/status`);
}

export async function deleteDocument(docId: string): Promise<{ deleted: boolean }> {
  return apiDelete(`/api/v1/admin/documents/${docId}`);
}
