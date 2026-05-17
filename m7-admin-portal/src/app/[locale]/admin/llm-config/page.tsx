/**
 * LLM Backend Configuration — manage AI model backends.
 * Data from Mock Server (Phase 1) or real M5 backend (Phase 2).
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import type { LLMBackend, LLMBackendType, LLMPurpose } from '@/types';
import { listBackends, createBackend, updateBackend, deleteBackend } from '@/lib/api/llm-config';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import { Cpu, Plus, Pencil, Trash2, Loader2, Wifi, CheckCircle2, XCircle } from 'lucide-react';

const BACKEND_TYPES: { value: LLMBackendType; label: string }[] = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'claude', label: 'Claude' },
  { value: 'ollama', label: 'Ollama' },
  { value: 'vllm', label: 'vLLM' },
  { value: 'lmstudio', label: 'LM Studio' },
  { value: 'custom', label: 'Custom' },
];

const PURPOSE_OPTIONS: { value: LLMPurpose; label: string }[] = [
  { value: 'chat', label: 'Chat / Generation' },
  { value: 'thinking', label: 'Thinking / Reasoning' },
  { value: 'embedding', label: 'Embedding' },
  { value: 'reranking', label: 'Reranking' },
  { value: 'ocr', label: 'OCR' },
  { value: 'vision', label: 'Vision / Multimodal' },
  { value: 'parsing', label: 'Document Parsing' },
];

const AGENTS = ['structure', 'machinery', 'piping', 'electrical', 'communication', 'automation'];

const emptyForm = (): Partial<LLMBackend> => ({
  backend_type: 'openai',
  purpose: 'chat' as LLMPurpose,
  model_name: '',
  base_url: '',
  api_key: '',
  max_tokens: 4096,
  temperature: 0.7,
  is_default: false,
  assigned_agents: [],
});

export default function LLMConfigPage() {
  const [backends, setBackends] = useState<LLMBackend[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<Partial<LLMBackend>>(emptyForm());
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const fetchBackends = useCallback(async () => {
    setLoading(true);
    try { const res = await listBackends(); setBackends(res.backends); }
    catch { setBackends([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchBackends(); }, [fetchBackends]);

  const openAdd = () => { setEditingId(null); setForm(emptyForm()); setDialogOpen(true); };
  const openEdit = (b: LLMBackend) => { setEditingId(b.backend_id); setForm({ ...b }); setDialogOpen(true); };

  const handleSave = async () => {
    if (!form.model_name?.trim()) return;
    setSaving(true);
    try {
      if (editingId) await updateBackend(editingId, form);
      else await createBackend(form);
      setDialogOpen(false);
      fetchBackends();
    } catch { /* handled by API client */ }
    finally { setSaving(false); }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    await deleteBackend(deleteTarget);
    setBackends((prev) => prev.filter((b) => b.backend_id !== deleteTarget));
    setDeleteTarget(null);
  };

  const updateField = <K extends keyof LLMBackend>(key: K, value: LLMBackend[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const toggleAgent = (agent: string) => {
    const current = form.assigned_agents || [];
    updateField('assigned_agents',
      current.includes(agent) ? current.filter((a) => a !== agent) : [...current, agent],
    );
  };

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">LLM Configuration</h1>
          <p className="text-sm text-muted-foreground mt-1">Manage AI model backends for different domain agents.</p>
        </div>
        <Button onClick={openAdd} size="sm" className="gap-1.5">
          <Plus className="h-4 w-4" /> Add Backend
        </Button>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground py-8 text-center">Loading...</p>
      ) : backends.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">No backends configured. Add one to get started.</p>
      ) : (
        <div className="grid gap-4">
          {backends.map((b) => (
            <Card key={b.backend_id}>
              <CardContent className="flex items-start justify-between p-5">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Cpu className="h-4 w-4 text-muted-foreground" />
                    <span className="font-semibold text-sm">{b.model_name}</span>
                    {b.purpose && <Badge className="text-[10px]">{b.purpose}</Badge>}
                    {b.is_default && <Badge variant="secondary" className="text-[10px]">Default</Badge>}
                    <Badge variant="outline" className="text-[10px]">{b.backend_type}</Badge>
                  </div>
                  {b.base_url && <p className="text-xs text-muted-foreground mt-1">URL: {b.base_url}</p>}
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Max {b.max_tokens} tokens · Temp {b.temperature}
                  </p>
                  {b.assigned_agents && b.assigned_agents.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-2">
                      {b.assigned_agents.map((a) => (
                        <Badge key={a} variant="secondary" className="text-[10px]">{a}</Badge>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex gap-1 ml-4 shrink-0">
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(b)}>
                    <Pencil className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setDeleteTarget(b.backend_id)}>
                    <Trash2 className="h-4 w-4 text-muted-foreground" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Add/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editingId ? 'Edit Backend' : 'Add Backend'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <label className="text-xs font-medium">Purpose</label>
              <select
                value={form.purpose || 'chat'}
                onChange={(e) => updateField('purpose', e.target.value as LLMPurpose)}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm"
              >
                {PURPOSE_OPTIONS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium">Backend Type</label>
              <select
                value={form.backend_type}
                onChange={(e) => updateField('backend_type', e.target.value as LLMBackendType)}
                className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm"
              >
                {BACKEND_TYPES.map((bt) => <option key={bt.value} value={bt.value}>{bt.label}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium">Model Name</label>
              <Input value={form.model_name || ''} onChange={(e) => updateField('model_name', e.target.value)}
                placeholder="e.g. deepseek-chat" className="mt-1" />
            </div>
            <div>
              <label className="text-xs font-medium">Base URL</label>
              <Input value={form.base_url || ''} onChange={(e) => updateField('base_url', e.target.value)}
                placeholder="e.g. https://api.deepseek.com" className="mt-1" />
            </div>
            <div>
              <label className="text-xs font-medium">API Key</label>
              <Input type="password" value={form.api_key || ''} onChange={(e) => updateField('api_key', e.target.value)}
                placeholder="sk-..." className="mt-1" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium">Max Tokens</label>
                <Input type="number" value={form.max_tokens || 4096}
                  onChange={(e) => updateField('max_tokens', parseInt(e.target.value) || 4096)} className="mt-1" />
              </div>
              <div>
                <label className="text-xs font-medium">Temperature ({form.temperature})</label>
                <input type="range" min="0" max="2" step="0.1" value={form.temperature || 0.7}
                  onChange={(e) => updateField('temperature', parseFloat(e.target.value))}
                  className="mt-2 w-full" />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <input type="checkbox" id="is-default" checked={form.is_default || false}
                onChange={(e) => updateField('is_default', e.target.checked)} />
              <label htmlFor="is-default" className="text-xs">Set as default backend</label>
            </div>
            <div>
              <label className="text-xs font-medium">Assigned Agents</label>
              <div className="flex flex-wrap gap-1.5 mt-1">
                {AGENTS.map((a) => (
                  <button
                    key={a}
                    onClick={() => toggleAgent(a)}
                    className={`rounded-full px-2.5 py-0.5 text-[11px] border transition-colors ${
                      (form.assigned_agents || []).includes(a)
                        ? 'bg-primary text-primary-foreground border-primary'
                        : 'bg-background text-muted-foreground border-border hover:bg-muted'
                    }`}
                  >
                    {a}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving || !form.model_name?.trim()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editingId ? 'Save' : 'Add'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Backend</DialogTitle>
            <div className="text-sm text-muted-foreground">Remove this LLM backend configuration?</div>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
