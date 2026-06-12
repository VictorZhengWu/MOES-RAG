/**
 * Project detail page — Overview / Conversations / Issues / Compliance / Documents.
 * Phase 4-B: Full tabbed workspace with real API integration.
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Loader2, ArrowLeft, Plus, Brain, CheckCircle2, AlertCircle, FileText } from 'lucide-react';

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function ProjectDetailPage() {
  const { id } = useParams<{ id: string }>();
  const locale = useLocale();
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
  const h: any = token ? { Authorization: `Bearer ${token}` } : {};

  const [project, setProject] = useState<any>(null);
  const [dash, setDash] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchProject = useCallback(async () => {
    setLoading(true);
    try {
      const pRes = await fetch(`${BASE_URL}/api/v1/projects/${id}`, { headers: h }).catch(() => null);
      const dRes = await fetch(`${BASE_URL}/api/v1/projects/${id}/dashboard`, { headers: h }).catch(() => null);
      if (pRes?.ok) setProject(await (pRes as Response).json());
      if (dRes?.ok) setDash(await (dRes as Response).json());
    } catch {}
    setLoading(false);
  }, [id, token]);

  useEffect(() => { fetchProject(); }, [fetchProject]);

  if (loading) return <div className="flex items-center gap-2 p-8 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin"/>Loading...</div>;
  if (!project) return <div className="p-8 text-sm text-destructive">Project not found</div>;

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <Button variant="ghost" size="sm" onClick={() => router.push(`/${locale}/projects`)}><ArrowLeft className="h-4 w-4"/></Button>
        <div>
          <h1 className="text-xl font-bold">{project.name}</h1>
          <div className="flex gap-1.5 mt-1">
            <Badge variant="secondary" className="text-[10px]">{project.type}</Badge>
            {project.primary_class && <Badge variant="outline" className="text-[10px]">{project.primary_class}</Badge>}
            <Badge variant="outline" className="text-[10px]">{project.phase}</Badge>
          </div>
        </div>
      </div>

      <Tabs defaultValue="overview">
        <TabsList className="mb-4">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="conversations">Conversations</TabsTrigger>
          <TabsTrigger value="issues">Issues</TabsTrigger>
          <TabsTrigger value="compliance">Compliance</TabsTrigger>
          <TabsTrigger value="casestudy">Case Study</TabsTrigger>
          <TabsTrigger value="comments">Comments</TabsTrigger>
          <TabsTrigger value="documents">Documents</TabsTrigger>
        </TabsList>

        {/* Overview tab — dashboard stats */}
        <TabsContent value="overview">
          <DashboardTab dash={dash} project={project} locale={locale} token={token} />
        </TabsContent>

        {/* Conversations tab */}
        <TabsContent value="conversations">
          <ConversationsTab projectId={id} locale={locale} router={router} token={token} />
        </TabsContent>

        {/* Issues tab — kanban-style */}
        <TabsContent value="issues">
          <IssuesTab projectId={id} locale={locale} token={token} router={router} />
        </TabsContent>

        {/* Compliance tab */}
        <TabsContent value="compliance">
          <ComplianceTab projectId={id} token={token} />
        </TabsContent>

        {/* Documents tab */}
        <TabsContent value="casestudy">
          <CaseStudyTab projectId={id} token={token} />
        </TabsContent>
        <TabsContent value="comments">
          <CommentsTab projectId={id} token={token} />
        </TabsContent>
        <TabsContent value="documents">
          <DocumentsTab projectId={id} token={token} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

// ---- Dashboard Tab ----

function DashboardTab({ dash, project, locale, token }: any) {
  const router = useRouter();
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard label="Conversations" value={dash?.conversation_count ?? '—'} />
        <StatCard label="Documents" value={dash?.document_count ?? '—'} />
        <StatCard label="Issues" value={dash?.issue_count ?? '—'} />
        <StatCard label="Compliance" value={dash?.compliance_pct != null ? `${dash.compliance_pct}%` : '—'} />
      </div>
      {dash?.compliance_total > 0 && (
        <div className="h-3 rounded-full bg-muted overflow-hidden">
          <div className="h-full rounded-full bg-green-500 transition-all" style={{ width: `${dash.compliance_pct || 0}%` }} />
        </div>
      )}
      <Button size="sm" onClick={() => router.push(`/${locale}/research?project=${project.project_id}&title=${encodeURIComponent(project.name || '')}`)} className="gap-1.5">
        <Brain className="h-3.5 w-3.5"/> Start Deep Research
      </Button>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: any }) {
  return (
    <Card><CardContent className="p-4 text-center">
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs text-muted-foreground">{label}</p>
    </CardContent></Card>
  );
}

// ---- Conversations Tab ----

function ConversationsTab({ projectId, locale, router, token }: any) {
  const [convs, setConvs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const h: any = token ? { Authorization: `Bearer ${token}` } : {};

  useEffect(() => {
    fetch(`${BASE_URL}/api/v1/projects/${projectId}/conversations`, { headers: h })
      .then(r => r.ok ? r.json() : []).then(setConvs).catch(() => {}).finally(() => setLoading(false));
  }, [projectId, token]);

  if (loading) return <Loader2 className="h-4 w-4 animate-spin"/>;

  return (
    <div className="space-y-2">
      <Button size="sm" onClick={() => router.push(`/${locale}/chat`)} className="gap-1.5 mb-2">
        <Plus className="h-3.5 w-3.5"/> New Conversation
      </Button>
      {convs.length === 0 ? (
        <p className="text-sm text-muted-foreground">No conversations linked yet.</p>
      ) : (
        convs.map((c: any) => (
          <Card key={c.conversation_id} className="cursor-pointer hover:border-primary/40"
            onClick={() => router.push(`/${locale}/chat/${c.conversation_id}`)}>
            <CardContent className="p-3 flex items-center justify-between">
              <div>
                <p className="text-sm font-medium">{c.conversation_id}</p>
                {c.folder_path && <p className="text-xs text-muted-foreground">{c.folder_path}</p>}
              </div>
              {c.tags && JSON.parse(typeof c.tags === 'string' ? c.tags : '[]').map((t: string) => (
                <Badge key={t} variant="outline" className="text-[10px]">{t}</Badge>
              ))}
            </CardContent>
          </Card>
        ))
      )}
    </div>
  );
}

// ---- Issues Tab (Kanban) ----

function IssuesTab({ projectId, locale, token, router }: any) {
  const [issues, setIssues] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const h: any = token ? { Authorization: `Bearer ${token}` } : {};

  const fetchIssues = useCallback(() => {
    fetch(`${BASE_URL}/api/v1/projects/${projectId}/issues`, { headers: h })
      .then(r => r.ok ? r.json() : []).then(setIssues).catch(() => {}).finally(() => setLoading(false));
  }, [projectId, token]);

  useEffect(() => { fetchIssues(); }, [fetchIssues]);

  const columns = ['pending', 'in_progress', 'resolved', 'closed'];
  const colLabels: Record<string, string> = { pending: 'Pending', in_progress: 'In Progress', resolved: 'Resolved', closed: 'Closed' };

  const [dragging, setDragging] = useState<string | null>(null);

  const moveIssue = async (issueId: string, newStatus: string) => {
    // Optimistic update
    setIssues(prev => prev.map(i => i.issue_id === issueId ? { ...i, status: newStatus } : i));
    try {
      await fetch(`${BASE_URL}/api/v1/projects/${projectId}/issues/${issueId}`, {
        method: 'PATCH', headers: { ...h, 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: newStatus }),
      });
    } catch {
      // Rollback on failure
      fetchIssues();
    }
  };

  const onDragStart = (issueId: string) => setDragging(issueId);
  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); };
  const onDrop = (col: string) => {
    if (dragging) moveIssue(dragging, col);
    setDragging(null);
  };

  if (loading) return <Loader2 className="h-4 w-4 animate-spin"/>;

  return (
    <div className="grid grid-cols-4 gap-4">
      {columns.map(col => (
        <div key={col} className={`rounded-lg border p-3 min-h-[200px] ${dragging ? 'bg-muted/30' : 'bg-muted/20'}`}
          onDragOver={onDragOver} onDrop={() => onDrop(col)}>
          <p className="text-xs font-semibold mb-2 flex items-center justify-between">
            {colLabels[col]}
            <Badge variant="secondary" className="text-[10px]">{issues.filter(i => i.status === col).length}</Badge>
          </p>
          <div className="space-y-2">
            {issues.filter(i => i.status === col).map(i => (
              <Card key={i.issue_id} className="p-2 text-xs cursor-grab active:cursor-grabbing"
                draggable onDragStart={() => onDragStart(i.issue_id)}>
                <p className="font-medium">{i.title}</p>
                <div className="flex gap-1 mt-1 items-center justify-between">
                  <div className="flex gap-1">
                    <Badge variant="outline" className="text-[9px]">{i.priority}</Badge>
                    {i.assignee && <Badge variant="secondary" className="text-[9px]">{i.assignee}</Badge>}
                  </div>
                  <span className="cursor-pointer" onClick={(e) => { e.stopPropagation(); router.push(`/${locale}/research?issue=${encodeURIComponent(i.title)}`); }}
                    title="Start Deep Research on this issue">
                    <Brain className="h-3 w-3 text-primary hover:opacity-70" />
                  </span>
                </div>
              </Card>
            ))}
            {issues.filter(i => i.status === col).length === 0 && (
              <p className="text-xs text-muted-foreground text-center py-4">—</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---- Compliance Tab ----

function ComplianceTab({ projectId, token }: any) {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const h: any = token ? { Authorization: `Bearer ${token}` } : {};

  useEffect(() => {
    fetch(`${BASE_URL}/api/v1/projects/${projectId}/compliance`, { headers: h })
      .then(r => r.ok ? r.json() : []).then(setItems).catch(() => {}).finally(() => setLoading(false));
  }, [projectId, token]);

  const statusIcon = (s: string) => s === 'verified' ? <CheckCircle2 className="h-4 w-4 text-green-500"/> :
    s === 'needs_review' ? <AlertCircle className="h-4 w-4 text-yellow-500"/> :
    <div className="h-4 w-4 rounded-full border-2 border-muted-foreground/30"/>;

  if (loading) return <Loader2 className="h-4 w-4 animate-spin"/>;

  const verified = items.filter(i => i.status === 'verified').length;
  const pct = items.length > 0 ? Math.round(verified / items.length * 100) : 0;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <div className="h-2 flex-1 rounded-full bg-muted overflow-hidden">
          <div className="h-full rounded-full bg-green-500 transition-all" style={{ width: `${pct}%` }} />
        </div>
        <span className="text-xs font-medium">{verified}/{items.length} ({pct}%)</span>
      </div>
      <div className="space-y-1">
        {items.map(item => (
          <div key={item.clause_id} className="flex items-center gap-2 px-3 py-1.5 rounded-lg hover:bg-muted/50 text-sm">
            {statusIcon(item.status)}
            <span className="flex-1 font-mono text-xs">{item.clause_ref}</span>
            {item.deviation_note && <Badge variant="outline" className="text-[9px] text-yellow-600">Deviation</Badge>}
          </div>
        ))}
      </div>
    </div>
  );
}

// ---- Documents Tab ----

function CaseStudyTab({ projectId, token }: any) {
  const h: any = token ? { Authorization: `Bearer ${token}` } : {};
  const [challenge, setChallenge] = useState('');
  const [solution, setSolution] = useState('');
  const [lessons, setLessons] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetch(`${BASE_URL}/api/v1/projects/${projectId}`, { headers: h })
      .then(r => r.json()).then(p => {
        setChallenge(p.case_challenge || ''); setSolution(p.case_solution || ''); setLessons(p.case_lessons || '');
      }).catch(() => {});
  }, [projectId]);

  const save = async () => {
    setSaving(true);
    await fetch(`${BASE_URL}/api/v1/projects/${projectId}/case-details`, {
      method: 'PATCH', headers: { ...h, 'Content-Type': 'application/json' },
      body: JSON.stringify({ case_challenge: challenge, case_solution: solution, case_lessons: lessons }),
    });
    setSaving(false); setSaved(true);
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Document key challenges, solutions, and lessons learned from this project.</p>
      <textarea className="w-full rounded-lg border px-3 py-2 text-sm" rows={3}
        placeholder="Key Challenge: What was the main technical challenge?" value={challenge}
        onChange={e => setChallenge(e.target.value)} />
      <textarea className="w-full rounded-lg border px-3 py-2 text-sm" rows={3}
        placeholder="Solution: How was it resolved?" value={solution}
        onChange={e => setSolution(e.target.value)} />
      <textarea className="w-full rounded-lg border px-3 py-2 text-sm" rows={3}
        placeholder="Lessons Learned: What would you do differently?" value={lessons}
        onChange={e => setLessons(e.target.value)} />
      <Button size="sm" onClick={save} disabled={saving}>
        {saving ? 'Saving...' : saved ? 'Saved ✓' : 'Save'}
      </Button>
    </div>
  );
}

function CommentsTab({ projectId, token }: any) {
  const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
  const h: any = token ? { Authorization: `Bearer ${token}` } : {};
  const [comments, setComments] = useState<any[]>([]);
  const [text, setText] = useState('');
  const [posting, setPosting] = useState(false);

  const fetchC = () => fetch(`${BASE_URL}/api/v1/projects/${projectId}/conclusions/__all__/comments`, { headers: h })
    .then(r => r.json()).then(setComments).catch(() => {});

  useEffect(() => { fetchC(); }, [projectId]);

  const post = async () => {
    if (!text.trim()) return;
    setPosting(true);
    // Extract @mentions: @username → store raw for now
    const mentions: string[] = [];
    const mentionRegex = /@(\w+)/g;
    let m;
    while ((m = mentionRegex.exec(text)) !== null) mentions.push(m[1]);

    await fetch(`${BASE_URL}/api/v1/projects/${projectId}/conclusions/__all__/comments`, {
      method: 'POST', headers: { ...h, 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: text, author_id: 'user', mentions }),
    });
    setText(''); setPosting(false); fetchC();
  };

  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Use @username to mention team members.</p>
      <div className="space-y-2 max-h-60 overflow-y-auto">
        {comments.map((c: any) => (
          <div key={c.comment_id} className="bg-muted/30 rounded-lg p-2 text-xs">
            <p className="font-medium text-muted-foreground">{c.author_id} &middot; {new Date(c.created_at * 1000).toLocaleString()}</p>
            <p>{c.content}</p>
          </div>
        ))}
        {comments.length === 0 && <p className="text-xs text-muted-foreground">No comments yet.</p>}
      </div>
      <div className="flex gap-2">
        <input className="flex-1 rounded-lg border px-3 py-2 text-xs" placeholder="Write a comment... Use @name to mention"
          value={text} onChange={e => setText(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !e.shiftKey && post()} />
        <Button size="sm" onClick={post} disabled={posting || !text.trim()}>{posting ? '...' : 'Post'}</Button>
      </div>
    </div>
  );
}

function DocumentsTab({ projectId, token }: any) {
  const [docs, setDocs] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const h: any = token ? { Authorization: `Bearer ${token}` } : {};

  useEffect(() => {
    fetch(`${BASE_URL}/api/v1/projects/${projectId}/documents`, { headers: h })
      .then(r => r.ok ? r.json() : []).then(setDocs).catch(() => {}).finally(() => setLoading(false));
  }, [projectId, token]);

  if (loading) return <Loader2 className="h-4 w-4 animate-spin"/>;

  return (
    <div>
      {docs.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          <FileText className="h-10 w-10 mx-auto mb-2 opacity-30"/>
          <p className="text-sm">No documents uploaded yet.</p>
        </div>
      ) : (
        <div className="space-y-1">
          {docs.map(d => (
            <div key={d.document_id} className="flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-muted/50 text-sm">
              <FileText className="h-4 w-4 text-muted-foreground"/>
              <span className="flex-1">{d.filename}</span>
              {d.discipline && <Badge variant="outline" className="text-[10px]">{d.discipline}</Badge>}
              <Badge variant="secondary" className="text-[10px]">{d.parse_status}</Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
