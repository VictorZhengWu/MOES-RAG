/**
 * Projects page — list, create, and manage marine engineering projects.
 * Phase 4-B: Real API integration replacing mock data.
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, Plus, Folder, Ship, Settings, ArrowRight } from 'lucide-react';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

interface Project {
  project_id: string;
  name: string;
  type: string;
  vessel_type: string;
  primary_class: string;
  phase: string;
  compliance_pct?: number;
  conversation_count?: number;
  document_count?: number;
  issue_count?: number;
  updated_at: number;
}

const TYPE_LABELS: Record<string, string> = {
  new_build: 'New Build', retrofit: 'Retrofit', maintenance: 'Maintenance',
  offshore: 'Offshore', research: 'Research', custom: 'Custom',
};
const PHASE_LABELS: Record<string, string> = {
  design: 'Design', construction: 'Construction', delivery: 'Delivery', operation: 'Operation',
};

export default function ProjectsPage() {
  const locale = useLocale();
  const router = useRouter();
  const token = useAuthStore((s) => s.token);

  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);

  // Create form
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newType, setNewType] = useState('custom');
  const [newVessel, setNewVessel] = useState('');
  const [newClass, setNewClass] = useState('DNV');
  const [newDesc, setNewDesc] = useState('');
  const [createErr, setCreateErr] = useState('');

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;
      const res = await fetch(`${BASE_URL}/api/v1/projects`, { headers });
      if (!res.ok) throw new Error(`Error ${res.status}`);
      const data = await res.json();
      setProjects(Array.isArray(data) ? data : []);
    } catch (e: any) {
      setError(e.message || 'Failed to load projects');
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { fetchProjects(); }, [fetchProjects]);

  const handleCreate = async () => {
    if (!newName.trim()) { setCreateErr('Name is required'); return; }
    setCreating(true);
    setCreateErr('');
    try {
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };
      const res = await fetch(`${BASE_URL}/api/v1/projects`, {
        method: 'POST', headers,
        body: JSON.stringify({
          name: newName.trim(),
          type: newType,
          vessel_type: newVessel || null,
          primary_class: newClass,
          description: newDesc,
          disciplines: [],
        }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail || `Error ${res.status}`);
      await fetchProjects();
      setShowCreate(false);
      setNewName(''); setNewDesc(''); setCreateErr('');
    } catch (e: any) {
      setCreateErr(e.message);
    } finally {
      setCreating(false);
    }
  };

  if (loading) return <div className="flex items-center gap-2 p-8 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading projects...</div>;

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-xl font-bold">Projects</h1>
        <Button size="sm" onClick={() => setShowCreate(true)} className="gap-1.5">
          <Plus className="h-4 w-4" /> New Project
        </Button>
      </div>

      {error && <div className="mb-4 text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</div>}

      {/* Create dialog */}
      {showCreate && (
        <Card className="mb-6"><CardContent className="p-4 space-y-3">
          <p className="text-sm font-medium">Create New Project</p>
          <div className="grid grid-cols-2 gap-3">
            <Input placeholder="Project name *" value={newName} onChange={(e) => setNewName(e.target.value)} className="h-8 text-sm" />
            <select value={newClass} onChange={(e) => setNewClass(e.target.value)} className="rounded-lg border px-3 py-1 h-8 text-sm">
              {['DNV','ABS','CCS','LR','BV'].map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <select value={newType} onChange={(e) => setNewType(e.target.value)} className="rounded-lg border px-3 py-1 h-8 text-sm">
              {Object.entries(TYPE_LABELS).map(([k,v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <Input placeholder="Vessel type (optional)" value={newVessel} onChange={(e) => setNewVessel(e.target.value)} className="h-8 text-sm" />
          </div>
          <Textarea placeholder="Description (optional)" value={newDesc} onChange={(e) => setNewDesc(e.target.value)} rows={2} className="resize-none text-sm" />
          {createErr && <p className="text-xs text-destructive">{createErr}</p>}
          <div className="flex gap-2">
            <Button size="sm" onClick={handleCreate} disabled={creating}>{creating ? <Loader2 className="h-3 w-3 animate-spin mr-1"/> : null}Create</Button>
            <Button size="sm" variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button>
          </div>
        </CardContent></Card>
      )}

      {/* Project list */}
      {projects.length === 0 ? (
        <div className="text-center py-16 text-muted-foreground">
          <Folder className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No projects yet. Create your first project to organize your research.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <Card key={p.project_id} className="cursor-pointer hover:border-primary/40 transition-colors"
              onClick={() => router.push(`/${locale}/projects/${p.project_id}`)}>
              <CardContent className="p-4 space-y-2">
                <div className="flex items-start justify-between">
                  <p className="text-sm font-semibold truncate">{p.name}</p>
                  <ArrowRight className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
                </div>
                <div className="flex gap-1.5 flex-wrap">
                  <Badge variant="secondary" className="text-[10px]">{TYPE_LABELS[p.type] || p.type}</Badge>
                  {p.primary_class && <Badge variant="outline" className="text-[10px]">{p.primary_class}</Badge>}
                  <Badge variant="outline" className="text-[10px]">{PHASE_LABELS[p.phase] || p.phase}</Badge>
                </div>
                {p.vessel_type && <p className="text-xs text-muted-foreground flex items-center gap-1"><Ship className="h-3 w-3" /> {p.vessel_type}</p>}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
