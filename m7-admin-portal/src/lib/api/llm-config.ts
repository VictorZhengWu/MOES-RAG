/**
 * LLM & Web Search configuration API functions.
 *
 * WHAT: Real API calls to M8's /admin/config endpoints for LLM backend
 *       and web search engine configuration. Replaces Phase 1 mock calls.
 *
 * WHY: M8 now has a unified config store in SQLite with hot-reload.
 *      Changes take effect immediately on the running M5 QAEngine.
 */

import type { LLMBackend } from '@/types';
import { apiGet, apiPost } from './client';

// ── LLM Backend ──────────────────────────────────────────────────────

export async function listBackends(): Promise<{ backends: LLMBackend[]; total: number }> {
  // M5 currently has ONE LLM backend — return as singleton list
  try {
    const data = await apiGet<Record<string, string>>('/admin/config/llm');
    return {
      backends: [{
        purpose: 'chat',
        provider: data.provider || 'deepseek',
        model: data.model || 'deepseek-chat',
        base_url: data.base_url || 'https://api.deepseek.com/v1',
        api_key: data.api_key || '',
        is_default: true,
      }],
      total: 1,
    };
  } catch {
    return { backends: [], total: 0 };
  }
}

export async function createBackend(data: Partial<LLMBackend>): Promise<LLMBackend> {
  return apiPost('/admin/config/llm', {
    provider: data.provider || 'deepseek',
    model: data.model || 'deepseek-chat',
    api_key: data.api_key || '',
    base_url: data.base_url || 'https://api.deepseek.com/v1',
  });
}

export async function updateBackend(
  _id: string, data: Partial<LLMBackend>,
): Promise<{ updated: boolean }> {
  await apiPost('/admin/config/llm', {
    provider: data.provider,
    model: data.model,
    api_key: data.api_key || '',
    base_url: data.base_url || '',
  });
  return { updated: true };
}

export async function deleteBackend(_id: string): Promise<{ deleted: boolean }> {
  return { deleted: true };  // Single backend — no deletion needed
}

// ── Web Search ────────────────────────────────────────────────────────

export async function getWebSearchConfig(): Promise<Record<string, string>> {
  return apiGet('/admin/config/web-search');
}

export async function updateWebSearchConfig(engine: string, apiKey?: string, searxngUrl?: string, googleCx?: string) {
  return apiPost('/admin/config/web-search', {
    engine,
    api_key: apiKey || null,
    searxng_url: searxngUrl || 'http://localhost:8888',
    google_cx: googleCx || null,
  });
}

export async function testWebSearchConnection(): Promise<{ ok: boolean; error?: string }> {
  return apiPost('/admin/config/web-search/test', {});
}

// ── Features ──────────────────────────────────────────────────────────

export async function getFeatures(): Promise<Record<string, string>> {
  return apiGet('/admin/config/features');
}

export async function updateFeatures(features: Record<string, boolean>) {
  return apiPost('/admin/config/features', features);
}

// ── SMTP ──────────────────────────────────────────────────────────────

export async function getSMTPConfig(): Promise<Record<string, string>> {
  return apiGet('/admin/config/smtp');
}

export async function updateSMTPConfig(smtp: Record<string, string | number>) {
  return apiPost('/admin/config/smtp', smtp);
}
