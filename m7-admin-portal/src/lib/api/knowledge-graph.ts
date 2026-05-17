import type { KGEntity, KGRelation } from '@/types';
import { apiGet } from './client';

export async function listEntities(): Promise<{ entities: KGEntity[]; total: number }> {
  return apiGet('/api/v1/admin/knowledge-graph/entities');
}

export async function listRelations(): Promise<{ relations: KGRelation[]; total: number }> {
  return apiGet('/api/v1/admin/knowledge-graph/relations');
}
