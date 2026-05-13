/**
 * Model listing API.
 *
 * WHY: M6's model selector dropdown in settings and the model parameter
 * in chat requests need this list. The /v1/models endpoint follows
 * the OpenAI-compatible format defined in contracts/.
 */

import type { ModelListResponse } from '@/types';
import { apiGet } from './client';

export async function listModels(): Promise<ModelListResponse> {
  return apiGet<ModelListResponse>('/v1/models');
}
