import type { SystemStats, ModuleHealth } from '@/types';
import { apiGet } from './client';

export async function getStats(): Promise<SystemStats> {
  return apiGet('/api/v1/admin/stats');
}

export async function getHealth(): Promise<{ status: string; version: string; modules: ModuleHealth; uptime_seconds: number }> {
  return apiGet('/api/v1/admin/health');
}
