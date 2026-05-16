import type { AdminUser } from '@/types';
import { apiGet, apiPost, apiDelete } from './client';

export async function listUsers(): Promise<{ users: AdminUser[]; total: number }> {
  return apiGet('/api/v1/admin/users');
}

export async function createUser(data: Record<string, unknown>): Promise<AdminUser> {
  return apiPost('/api/v1/admin/users', data);
}

export async function deleteUser(userId: string): Promise<{ deleted: boolean }> {
  return apiDelete(`/api/v1/admin/users/${userId}`);
}
