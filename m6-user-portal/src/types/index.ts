/**
 * Shared TypeScript type definitions for M6 User Portal.
 *
 * WHY: Centralized types prevent drift between API client, stores,
 * and components. Types mirror contracts/ Pydantic schemas exactly,
 * ensuring frontend-backend alignment when switching from Mock Server
 * to real M5 API in Phase 2.
 */

// ── Chat ───────────────────────────────────────────────────────────

export interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
  /** Server-generated message ID for jump-navigation targeting */
  id?: string;
}

export interface Citation {
  index: number;
  source_doc: string;
  section: string;
  clause_id?: string;
  excerpt: string;
  url?: string;
}

export interface ChatRequest {
  model: string;
  messages: Message[];
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
  conversation_id?: string;
  domain_filter?: string;
  vessel_type_filter?: string;
  /** Enable web search augmentation (Phase 2) */
  web_search?: boolean;
}

export interface ChatResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: Choice[];
  usage?: Usage;
  citations: Citation[];
}

export interface Choice {
  index: number;
  message: Message;
  finish_reason: string;
}

export interface Usage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

// ── Streaming ──────────────────────────────────────────────────────

export interface StreamChunk {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: StreamChoice[];
}

export interface StreamChoice {
  index: number;
  delta: { content?: string };
  finish_reason: string | null;
}

// ── Auth ────────────────────────────────────────────────────────────

export interface UserProfile {
  user_id: string;
  username: string;
  email: string;
  avatar_url?: string;
  role: 'admin' | 'editor' | 'viewer';
}

export type AuthStatus = 'loading' | 'guest' | 'authenticated';

// ── File Upload ─────────────────────────────────────────────────────

export interface FileAttachment {
  file: File;
  previewUrl: string;
  status: 'pending' | 'uploading' | 'uploaded' | 'error';
}

// ── Conversations ──────────────────────────────────────────────────

export interface ConversationSummary {
  conversation_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ConversationListResponse {
  conversations: ConversationSummary[];
  total: number;
}

export interface ConversationDetailResponse {
  conversation_id: string;
  messages: Message[];
}

// ── Models ─────────────────────────────────────────────────────────

export interface ModelInfo {
  id: string;
  object: string;
  created: number;
  owned_by: string;
}

export interface ModelListResponse {
  object: string;
  data: ModelInfo[];
}

// ── Knowledge Base ─────────────────────────────────────────────────

export interface DocumentInfo {
  doc_id: string;
  source_filename: string;
  classification_society: string | null;
  regulation_name: string | null;
  version_year: number | null;
  domain: string;
  chunks_count: number;
  ingested_at: string;
  status: string;
}

export interface DocumentListResponse {
  documents: DocumentInfo[];
  total: number;
}

// ── User Settings ──────────────────────────────────────────────────

export interface UserSettings {
  language: string;
  theme: string;
}

// ── Supported Languages ─────────────────────────────────────────────

export type SupportedLanguage = 'en' | 'zh' | 'ko' | 'ja' | 'no';

export const SUPPORTED_LANGUAGES: { code: SupportedLanguage; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'zh', label: '中文' },
  { code: 'ko', label: '한국어' },
  { code: 'ja', label: '日本語' },
  { code: 'no', label: 'Norsk' },
];

// ── Jump Navigation ─────────────────────────────────────────────────

export interface JumpEntry {
  index: number;
  messageId: string;
  /** First ~60 chars of the user's question */
  preview: string;
}
