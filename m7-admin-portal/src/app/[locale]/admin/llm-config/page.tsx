/**
 * LLM Configuration — 7 purpose boxes in a single page.
 * Each box configures one model purpose with purpose-specific fields.
 * Data saved to Mock Server (Phase 1) or relational DB (Phase 2).
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import type { LLMBackend } from '@/types';
import { listBackends, createBackend, updateBackend } from '@/lib/api/llm-config';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Loader2, CheckCircle2, XCircle, AlertCircle,
  MessageSquare, Brain, Layers, ArrowUpDown, ScanText, Eye, FileText,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────

type Provider = 'openai_compatible' | 'ollama' | 'vllm' | 'lmstudio' | 'none';

const PROVIDERS: { value: Provider; label: string }[] = [
  { value: 'openai_compatible', label: 'OpenAI Compatible' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'vllm', label: 'vLLM' },
  { value: 'lmstudio', label: 'LM Studio' },
];

const PROVIDERS_WITH_NONE: { value: Provider; label: string }[] = [
  { value: 'none', label: 'None (disabled)' },
  ...PROVIDERS,
];

type ConnectionStatus = 'idle' | 'testing' | 'connected' | 'failed';

interface BoxConfig {
  purpose: string;
  provider: Provider;
  model_name: string;
  api_key: string;
  base_url: string;
  // Chat/Thinking
  temperature?: number;
  max_tokens?: number;
  // Embedding
  embedding_dim?: number;
  chunk_size?: number;
  chunk_overlap?: number;
  // Reranking
  top_n?: number;
  match_threshold?: number;
}

const defaultConfig = (purpose: string): BoxConfig => ({
  purpose,
  provider: purpose === 'reasoning' || purpose === 'vision' ? 'none' : 'openai_compatible',
  model_name: '',
  api_key: '',
  base_url: '',
  temperature: 0.5,
  max_tokens: 4096,
  embedding_dim: undefined,
  chunk_size: 800,
  chunk_overlap: 100,
  top_n: 5,
  match_threshold: undefined,
});

// ── Purpose definitions ─────────────────────────────────────────────

interface PurposeDef {
  purpose: string;
  icon: typeof MessageSquare;
  label: string;
  canDisable: boolean;
  noApiKey?: boolean;
}

const PURPOSES: PurposeDef[] = [
  { purpose: 'chat', icon: MessageSquare, label: 'Chat Model', canDisable: false,
    fields: ['provider', 'api_key', 'model_name', 'temperature', 'test'] },
  { purpose: 'thinking', icon: Brain, label: 'Reasoning Model', canDisable: true,
    fields: ['provider', 'api_key', 'model_name', 'test'] },
  { purpose: 'embedding', icon: Layers, label: 'Embedding Model', canDisable: false,
    fields: ['provider', 'api_key', 'model_name', 'embedding_dim', 'chunk_size', 'chunk_overlap', 'test'] },
  { purpose: 'reranking', icon: ArrowUpDown, label: 'Reranking Model', canDisable: false,
    fields: ['provider', 'api_key', 'model_name', 'top_n', 'match_threshold', 'test'] },
  { purpose: 'ocr', icon: ScanText, label: 'OCR Model', canDisable: false,
    fields: ['provider', 'api_key', 'model_name', 'test'] },
  { purpose: 'vision', icon: Eye, label: 'Vision / Multimodal Model', canDisable: true,
    fields: ['provider', 'api_key', 'model_name', 'test'] },
  { purpose: 'parsing', icon: FileText, label: 'Document Parsing Engine', canDisable: false,
    fields: ['provider', 'test'], noApiKey: true },
];

const PARSING_ENGINES = [
  { value: 'docling', label: 'Docling' },
  { value: 'mineru', label: 'MinerU' },
  { value: 'marker', label: 'Marker' },
  { value: 'unstructured', label: 'Unstructured' },
];

// ── Component ──────────────────────────────────────────────────────

export default function LLMConfigPage() {
  const [configs, setConfigs] = useState<Record<string, BoxConfig>>({});
  const [statuses, setStatuses] = useState<Record<string, ConnectionStatus>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);

  // Load from API → init form state
  const loadConfigs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listBackends();
      const map: Record<string, BoxConfig> = {};
      // Initialize defaults for all 7 purposes
      PURPOSES.forEach((p) => { map[p.purpose] = defaultConfig(p.purpose); });
      // Override with API data
      res.backends.forEach((b: LLMBackend) => {
        if (map[b.purpose]) {
          map[b.purpose] = {
            ...map[b.purpose],
            provider: (b.backend_type as Provider) || 'openai_compatible',
            model_name: b.model_name || '',
            api_key: b.api_key || '',
            base_url: b.base_url || '',
            temperature: b.temperature ?? 0.5,
            max_tokens: b.max_tokens ?? 4096,
          };
        }
      });
      setConfigs(map);
    } catch {
      const map: Record<string, BoxConfig> = {};
      PURPOSES.forEach((p) => { map[p.purpose] = defaultConfig(p.purpose); });
      setConfigs(map);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadConfigs(); }, [loadConfigs]);

  const updateField = (purpose: string, field: string, value: unknown) => {
    setConfigs((prev) => ({ ...prev, [purpose]: { ...prev[purpose], [field]: value } }));
  };

  const handleSave = async (purpose: string) => {
    const cfg = configs[purpose];
    if (!cfg) return;
    setSaving(purpose);
    try {
      await (cfg.provider === 'none'
        ? updateBackend(`${purpose}-disabled`, { purpose, backend_type: 'none', model_name: '', is_default: false } as Partial<LLMBackend>)
        : createBackend({
          purpose, backend_type: cfg.provider, model_name: cfg.model_name,
          api_key: cfg.api_key, base_url: cfg.base_url,
          temperature: cfg.temperature, max_tokens: cfg.max_tokens,
        } as Partial<LLMBackend>)
      );
    } catch { /* Mock — always succeeds */ }
    setSaving(null);
  };

  const handleTest = async (purpose: string) => {
    setStatuses((prev) => ({ ...prev, [purpose]: 'testing' }));
    // Phase 1: mock test — always succeeds after 1s delay
    await new Promise((r) => setTimeout(r, 800));
    const cfg = configs[purpose];
    const ok = cfg && cfg.provider !== 'none' && cfg.model_name.trim() !== '';
    setStatuses((prev) => ({ ...prev, [purpose]: ok ? 'connected' : 'failed' }));
  };

  const statusIcon = (s: ConnectionStatus) => {
    if (s === 'testing') return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />;
    if (s === 'connected') return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    if (s === 'failed') return <XCircle className="h-4 w-4 text-red-500" />;
    return <AlertCircle className="h-4 w-4 text-yellow-500" />;
  };

  if (loading) return <div className="p-8 text-sm text-muted-foreground">Loading...</div>;

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-xl font-bold">LLM Configuration</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Configure one model backend for each purpose. The system calls the appropriate model based on the task.
        </p>
      </div>

      <div className="grid gap-6 max-w-2xl">
        {PURPOSES.map((pDef) => {
          const cfg = configs[pDef.purpose];
          if (!cfg) return null;
          const Icon = pDef.icon;
          const disabled = pDef.canDisable && cfg.provider === 'none';
          const status = statuses[pDef.purpose] || 'idle';

          return (
            <Card key={pDef.purpose} id={pDef.purpose}>
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Icon className="h-5 w-5 text-muted-foreground" />
                    <CardTitle className="text-base">{pDef.label}</CardTitle>
                  </div>
                  <div className="flex items-center gap-2">
                    {statusIcon(status)}
                    <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => handleTest(pDef.purpose)} disabled={disabled}>
                      Test Connection
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                {/* Provider */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">
                      {pDef.purpose === 'parsing' ? 'Engine' : 'Provider'}
                    </label>
                    <select
                      value={pDef.purpose === 'parsing' ? 'docling' : cfg.provider}
                      onChange={(e) => updateField(pDef.purpose, 'provider', e.target.value)}
                      className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm"
                      disabled={pDef.purpose === 'parsing'} // parsing is fixed
                    >
                      {pDef.purpose === 'parsing'
                        ? PARSING_ENGINES.map((pe) => <option key={pe.value} value={pe.value}>{pe.label}</option>)
                        : (pDef.canDisable ? PROVIDERS_WITH_NONE : PROVIDERS).map((pr) => <option key={pr.value} value={pr.value}>{pr.label}</option>)
                      }
                    </select>
                  </div>

                  {/* API Key — not for parsing */}
                  {!pDef.noApiKey && (
                    <div className={disabled ? 'opacity-40 pointer-events-none' : ''}>
                      <label className="text-xs font-medium text-muted-foreground">API Key</label>
                      <Input
                        type="password"
                        value={cfg.api_key}
                        onChange={(e) => updateField(pDef.purpose, 'api_key', e.target.value)}
                        placeholder="sk-..."
                        className="mt-1 h-9 text-sm"
                        disabled={disabled}
                      />
                    </div>
                  )}
                </div>

                {/* Model Name — not for parsing */}
                {!pDef.noApiKey && (
                  <div className={disabled ? 'opacity-40 pointer-events-none' : ''}>
                    <label className="text-xs font-medium text-muted-foreground">Model Name</label>
                    <Input
                      value={cfg.model_name}
                      onChange={(e) => updateField(pDef.purpose, 'model_name', e.target.value)}
                      placeholder={pDef.purpose === 'embedding' ? 'e.g. bge-m3' : pDef.purpose === 'reranking' ? 'e.g. bge-reranker-v2-m3' : 'e.g. deepseek-chat'}
                      className="mt-1 h-9 text-sm"
                      disabled={disabled}
                    />
                  </div>
                )}

                {/* Temperature — Chat only */}
                {pDef.purpose === 'chat' && (
                  <div>
                    <label className="text-xs font-medium text-muted-foreground">Temperature ({cfg.temperature})</label>
                    <input type="range" min="0" max="2" step="0.1" value={cfg.temperature || 0.5}
                      onChange={(e) => updateField(pDef.purpose, 'temperature', parseFloat(e.target.value))}
                      className="mt-1 w-full" />
                  </div>
                )}

                {/* Embedding-specific */}
                {pDef.purpose === 'embedding' && (
                  <div className="grid grid-cols-3 gap-3">
                    <div>
                      <label className="text-xs font-medium text-muted-foreground">Embedding Dim</label>
                      <Input type="number" value={cfg.embedding_dim || ''}
                        onChange={(e) => updateField(pDef.purpose, 'embedding_dim', parseInt(e.target.value) || undefined)}
                        placeholder="Auto" className="mt-1 h-9 text-sm" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground">Chunk Size</label>
                      <Input type="number" value={cfg.chunk_size || 800}
                        onChange={(e) => updateField(pDef.purpose, 'chunk_size', parseInt(e.target.value) || 800)}
                        className="mt-1 h-9 text-sm" />
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground">Chunk Overlap</label>
                      <Input type="number" value={cfg.chunk_overlap || 100}
                        onChange={(e) => updateField(pDef.purpose, 'chunk_overlap', parseInt(e.target.value) || 100)}
                        className="mt-1 h-9 text-sm" />
                    </div>
                  </div>
                )}

                {/* Reranking-specific */}
                {pDef.purpose === 'reranking' && (
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-xs font-medium text-muted-foreground">Top-N</label>
                      <div className="flex items-center gap-2 mt-1">
                        <input type="range" min="1" max="20" step="1" value={cfg.top_n || 5}
                          onChange={(e) => updateField(pDef.purpose, 'top_n', parseInt(e.target.value))}
                          className="flex-1" />
                        <span className="text-sm w-6 text-right">{cfg.top_n || 5}</span>
                      </div>
                    </div>
                    <div>
                      <label className="text-xs font-medium text-muted-foreground">Match Threshold</label>
                      <Input type="number" value={cfg.match_threshold || ''}
                        onChange={(e) => { const v = parseFloat(e.target.value); updateField(pDef.purpose, 'match_threshold', (v >= 0 && v <= 1) ? v : undefined); }}
                        placeholder="No threshold" step="0.05" min="0" max="1" className="mt-1 h-9 text-sm" />
                    </div>
                  </div>
                )}

                <Separator />
                <div className="flex justify-end">
                  <Button size="sm" onClick={() => handleSave(pDef.purpose)} disabled={saving === pDef.purpose}>
                    {saving === pDef.purpose && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />}
                    Save
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}
