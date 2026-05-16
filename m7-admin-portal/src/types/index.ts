/** Admin-specific types mirroring contracts/api_schemas.py */

export interface ParseTask {
  task_id: string; doc_id: string; status: string;
  progress_pct: number; chunks_count: number;
  error_message?: string; started_at?: string; completed_at?: string;
}

export interface DocumentRecord {
  doc_id: string; source_filename: string;
  classification_society?: string; regulation_name?: string;
  version_year?: number; domain: string;
  chunks_count: number; ingested_at: string; status: string;
}

export interface KGEntity {
  entity_id: string; name: string; entity_type: string;
  properties: Record<string, unknown>; source_doc_id?: string;
}

export interface KGRelation {
  relation_id: string; source_entity_id: string; target_entity_id: string;
  relation_type: string; source_entity_name: string; target_entity_name: string;
  confidence: number;
}

export interface LLMBackend {
  backend_id: string; backend_type: string; model_name: string;
  base_url?: string; api_key?: string; max_tokens: number;
  temperature: number; is_default: boolean; assigned_agents: string[];
}

export type LLMBackendType = 'openai' | 'deepseek' | 'claude' | 'ollama' | 'vllm' | 'lmstudio' | 'custom';

export interface AdminUser {
  user_id: string; username: string; email: string;
  role: 'admin' | 'editor' | 'viewer'; is_active: boolean;
  api_key_count: number; total_queries: number; created_at: string;
}

export interface SystemStats {
  total_documents: number; total_chunks: number;
  total_entities: number; total_relations: number;
  total_conversations: number; total_users: number;
  storage_size_bytes: number; avg_retrieval_latency_ms: number;
}

export interface ModuleHealth {
  m1_doc_parsing: string; m2_storage: string; m3_retrieval: string;
  m4_knowledge_graph: string; m5_qa_engine: string; m8_api_gateway: string;
}

export type SupportedLanguage = 'en' | 'zh' | 'ko' | 'ja' | 'no';
export const SUPPORTED_LANGUAGES = [
  { code: 'en' as SupportedLanguage, label: 'English' },
  { code: 'zh' as SupportedLanguage, label: '中文' },
  { code: 'ko' as SupportedLanguage, label: '한국어' },
  { code: 'ja' as SupportedLanguage, label: '日本語' },
  { code: 'no' as SupportedLanguage, label: 'Norsk' },
];
