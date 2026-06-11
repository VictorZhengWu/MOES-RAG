/**
 * Deep Research page — multi-step research with SSE progress.
 * Phase 4-A: Planner → Retrieval → Analysis → Report
 */
'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, Brain, FileText, Globe, CheckCircle2, AlertCircle } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ResearchPlan {
  sub_questions: Array<{ id: number; question: string; search_strategy: string[]; search_query: string }>;
  estimated_runtime_seconds: number;
}

interface ProgressData {
  phase: string;
  progress: number;
  message: string;
  regulation_count?: number;
  web_count?: number;
  conflicts_count?: number;
  plan?: ResearchPlan;
}

interface ReportSection {
  delta: string;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

export default function ResearchPage() {
  const t = useTranslations();
  const locale = useLocale();
  const token = useAuthStore((s) => s.token);
  const [query, setQuery] = useState('');
  const [running, setRunning] = useState(false);
  const [phase, setPhase] = useState('');
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [report, setReport] = useState('');
  const [plan, setPlan] = useState<ResearchPlan | null>(null);
  const [regCount, setRegCount] = useState(0);
  const [webCount, setWebCount] = useState(0);
  const [conflictCount, setConflictCount] = useState(0);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [reportId, setReportId] = useState('');
  const [includeCases, setIncludeCases] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const handleStart = useCallback(async () => {
    if (!query.trim() || running) return;
    setRunning(true);
    setDone(false);
    setReport('');
    setError('');
    setProgress(0);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${BASE_URL}/api/v1/agent/research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ query: query.trim(), stream: true, include_cases: includeCases }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setError(err.detail || `Error ${res.status}`);
        setRunning(false);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) { setError('No response stream'); setRunning(false); return; }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done: streamDone, value } = await reader.read();
        if (streamDone) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            const eventType = line.slice(7).trim();
            // The next line should be data:
            continue;
          }
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              handleSSEEvent(data, setPhase, setProgress, setMessage,
                setPlan, setRegCount, setWebCount, setConflictCount,
                setReport, setDone, setError, setReportId);
            } catch { /* skip malformed */ }
          }
        }
      }
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'Research failed');
      }
    } finally {
      setRunning(false);
    }
  }, [query, running, token]);

  const handleStop = () => {
    abortRef.current?.abort();
    setRunning(false);
  };

  const phaseLabel = {
    planning: 'Creating research plan...',
    retrieving: 'Searching regulations and web...',
    analyzing: 'Cross-referencing and detecting conflicts...',
    reporting: 'Generating report...',
  }[phase] || message;

  const progressPct = Math.round(progress * 100);

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="flex items-center gap-2 mb-6">
        <Brain className="h-6 w-6 text-primary" />
        <h1 className="text-xl font-bold">Deep Research</h1>
      </div>

      {/* Input */}
      {!running && !done && (
        <Card className="mb-6">
          <CardContent className="p-4 space-y-3">
            <Textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your research question. For best results, include specific regulation references (e.g., DNV Pt.3 Ch.3, ABS Pt.5B) and mention all classification societies you want to compare."
              rows={4}
              className="resize-none"
              disabled={running}
            />
            <div className="flex items-center gap-3">
              <Button onClick={handleStart} disabled={!query.trim() || running} className="gap-2">
                <Brain className="h-4 w-4" />
                Start Research
              </Button>
              <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
                <input type="checkbox" checked={includeCases} onChange={e => setIncludeCases(e.target.checked)}
                  className="h-3.5 w-3.5 rounded" />
                Include case studies
              </label>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Progress */}
      {running && (
        <Card className="mb-6">
          <CardContent className="p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              <span className="text-sm font-medium">{phaseLabel}</span>
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div className="h-full rounded-full bg-primary transition-all duration-500"
                style={{ width: `${progressPct}%` }} />
            </div>
            <p className="text-xs text-muted-foreground">{progressPct}% complete</p>
            <Button variant="outline" size="sm" onClick={handleStop}>Stop</Button>
          </CardContent>
        </Card>
      )}

      {/* Plan preview (during planning phase) */}
      {plan && phase === 'planning' && (
        <Card className="mb-6"><CardContent className="p-4 space-y-2">
          <p className="text-sm font-medium">Research Plan ({plan.sub_questions.length} sub-questions, ~{plan.estimated_runtime_seconds}s)</p>
          {plan.sub_questions.map((sq) => (
            <div key={sq.id} className="flex items-start gap-2 text-sm">
              <Badge variant="outline" className="text-[10px] shrink-0 mt-0.5">
                {sq.search_strategy.join('+')}
              </Badge>
              <span>{sq.question}</span>
            </div>
          ))}
        </CardContent></Card>
      )}

      {/* Stats (after retrieval) */}
      {(regCount > 0 || webCount > 0) && (
        <div className="flex gap-3 mb-6">
          <Badge variant="secondary"><FileText className="h-3 w-3 mr-1" /> {regCount} regulations</Badge>
          <Badge variant="secondary"><Globe className="h-3 w-3 mr-1" /> {webCount} web results</Badge>
          {conflictCount > 0 && (
            <Badge variant="outline" className="text-yellow-600 border-yellow-600">
              <AlertCircle className="h-3 w-3 mr-1" /> {conflictCount} conflicts
            </Badge>
          )}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 mb-6 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Report */}
      {report && (
        <Card>
          <CardContent className="p-6 prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {report}
            </ReactMarkdown>
          </CardContent>
        </Card>
      )}

      {/* Done state */}
      {done && (
        <div className="mt-4 space-y-4">
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground flex items-center gap-1">
              <CheckCircle2 className="h-4 w-4 text-green-500" />
              Research complete
            </span>
            <SaveToProjectButton report={report} token={token || ''} />
            <ExportPdfButton report={report} reportId={reportId} />
          </div>
          <QuestionConclusion report={report} reportId={reportId} token={token || ''} />
        </div>
      )}
    </div>
  );
}

// ---- SSE event handler ----

function handleSSEEvent(
  data: any,
  setPhase: (s: string) => void,
  setProgress: (n: number) => void,
  setMessage: (s: string) => void,
  setPlan: (p: ResearchPlan | null) => void,
  setRegCount: (n: number) => void,
  setWebCount: (n: number) => void,
  setConflictCount: (n: number) => void,
  setReport: (s: string | ((prev: string) => string)) => void,
  setDone: (b: boolean) => void,
  setError: (s: string) => void,
  setReportId: (s: string) => void,
) {
  if (data.phase) setPhase(data.phase);
  if (data.progress !== undefined) setProgress(data.progress);
  if (data.message) setMessage(data.message);
  if (data.report_id) setReportId(data.report_id);
  if (data.plan) setPlan(data.plan);
  if (data.regulation_count !== undefined) setRegCount(data.regulation_count);
  if (data.web_count !== undefined) setWebCount(data.web_count);
  if (data.conflicts_count !== undefined) setConflictCount(data.conflicts_count);

  if (data.delta) {
    setReport((prev: string) => prev + data.delta);
  }
  if (data.full_report) {
    setReport(data.full_report);
    setDone(true);
  }
  if (data.error) {
    setError(data.error);
  }
}

// ---- Simple Markdown renderer (bold, lists, headers, tables) ----

function QuestionConclusion({ report, reportId, token }: { report: string; reportId: string; token: string }) {
  const [expanded, setExpanded] = useState<number | null>(null);
  const [question, setQuestion] = useState('');
  const [asking, setAsking] = useState(false);
  const [answer, setAnswer] = useState('');
  const [evidence, setEvidence] = useState<any>(null);
  const [error, setError] = useState('');

  const conclusions = report.split('\n').filter((l: string) => l.match(/^- \*\*|^-\s+\*\*|^##\s+/));
  if (conclusions.length === 0) return null;

  const handleAsk = async () => {
    if (!question.trim() || expanded === null) return;
    setAsking(true); setError(''); setAnswer(''); setEvidence(null);
    try {
      const res = await fetch(`${BASE_URL}/api/v1/agent/research/${reportId}/question`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ conclusion_id: expanded, question: question.trim() }),
      });
      if (!res.ok) {
        const errText = await res.text().catch(() => '');
        setError(`Re-analysis failed: ${res.status === 503 ? 'AI engine is not available. Please try again later.' : res.status === 400 ? 'Invalid question format. Please rephrase.' : `Server error (${res.status}). Please wait and retry.`}`);
        return;
      }
      const data = await res.json();
      setAnswer(data.updated_analysis || 'Analysis updated.');
      setEvidence(data.evidence || null);
    } catch {
      setError('Cannot reach the server. Check your network connection and try again.');
    } finally { setAsking(false); }
  };

  return (
    <div className="rounded-lg border bg-muted/20 p-4">
      <p className="text-sm font-medium mb-2">Question a Conclusion</p>
      <p className="text-xs text-muted-foreground mb-3">Click a conclusion to expand it, then ask a follow-up question.</p>
      <div className="space-y-1 max-h-40 overflow-y-auto mb-3">
        {conclusions.slice(0, 8).map((c: string, i: number) => (
          <div key={i} className={`text-xs px-2 py-1 rounded cursor-pointer ${expanded === i ? 'bg-primary/10 border border-primary/30' : 'hover:bg-muted'}`}
            onClick={() => { setExpanded(expanded === i ? null : i); setQuestion(''); setAnswer(''); setEvidence(null); setError(''); }}>
            {c.slice(0, 120)}{c.length > 120 ? '...' : ''}
          </div>
        ))}
      </div>
      {expanded !== null && (
        <div className="space-y-2">
          <textarea value={question} onChange={e => setQuestion(e.target.value.slice(0, 500))}
            placeholder="What's your question about this conclusion? (max 500 chars)"
            rows={2} className="w-full rounded-lg border px-3 py-2 text-xs resize-none"
            disabled={asking} />
          <div className="flex items-center gap-2">
            <button onClick={handleAsk} disabled={asking || !question.trim()}
              className="px-3 py-1 text-xs rounded bg-primary text-primary-foreground disabled:opacity-50">
              {asking ? 'Analyzing...' : 'Ask'}
            </button>
            {error && <span className="text-xs text-destructive">{error}</span>}
          </div>
          {/* P0-4: Show evidence from research context */}
          {evidence && (
            <div className="space-y-2 mt-2">
              {evidence.regulation_results?.length > 0 && (
                <details className="text-xs"><summary className="cursor-pointer font-medium text-muted-foreground">Original Search Results ({evidence.regulation_results.length} items)</summary>
                  <div className="mt-1 space-y-1 max-h-32 overflow-y-auto">
                    {evidence.regulation_results.map((r: any, i: number) => (
                      <div key={i} className="bg-muted/30 rounded px-2 py-1">
                        <span className="text-[10px] text-muted-foreground">[{r.source}]</span> {r.text}
                      </div>
                    ))}
                  </div>
                </details>
              )}
              {evidence.web_results?.length > 0 && (
                <details className="text-xs"><summary className="cursor-pointer font-medium text-muted-foreground">Web References ({evidence.web_results.length} items)</summary>
                  <div className="mt-1 space-y-1">
                    {evidence.web_results.map((r: any, i: number) => (
                      <div key={i} className="bg-muted/30 rounded px-2 py-1">{r.title}: {r.snippet}</div>
                    ))}
                  </div>
                </details>
              )}
              {evidence.conflicts?.length > 0 && (
                <details className="text-xs"><summary className="cursor-pointer font-medium text-yellow-600">⚠ Conflicts Detected ({evidence.conflicts.length})</summary>
                  <div className="mt-1 space-y-1">
                    {evidence.conflicts.map((c: any, i: number) => (
                      <div key={i} className="bg-yellow-50 dark:bg-yellow-900/20 rounded px-2 py-1">
                        {c.parameter}: {c.society_a}={c.value_a} vs {c.society_b}={c.value_b} ({c.difference_pct}% diff)
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}
          {answer && (
            <div className="text-xs bg-background rounded-lg p-2 border">
              <p className="font-medium text-green-600 mb-1">🕐 Updated analysis (manual review) — {new Date().toLocaleString()}</p>
              {answer}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ExportPdfButton({ report, reportId }: { report: string; reportId: string }) {
  const [exporting, setExporting] = useState(false);
  if (!reportId) return null;

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch(`${BASE_URL}/api/v1/agent/research/${reportId}/export`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ report }),
      });
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, '_blank');
    } catch {} finally { setExporting(false); }
  };

  return (
    <button onClick={handleExport} disabled={exporting}
      className="px-3 py-1 text-xs rounded border hover:bg-muted">
      {exporting ? 'Exporting...' : 'Export PDF'}
    </button>
  );
}

function SaveToProjectButton({ report, token }: { report: string; token: string }) {
  const [projects, setProjects] = useState<any[]>([]);
  const [selected, setSelected] = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open || !token) return;
    const h: any = token ? { Authorization: `Bearer ${token}` } : {};
    fetch(`${BASE_URL}/api/v1/projects`, { headers: h })
      .then(r => r.ok ? r.json() : []).then(setProjects).catch(() => {});
  }, [open, token]);

  const handleSave = async () => {
    if (!selected || !token) return;
    setSaving(true);
    const h: any = { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` };
    try {
      await fetch(`${BASE_URL}/api/v1/projects/${selected}/conclusions`, {
        method: 'POST', headers: h,
        body: JSON.stringify({ text: 'Deep Research report', detail: report.slice(0, 500), source_type: 'deep_research', status: 'important' }),
      });
      setSaved(true);
    } catch {} finally { setSaving(false); }
  };

  if (saved) return <span className="text-sm text-green-600 font-medium">✓ Saved to project</span>;

  if (!open) return <Button size="sm" variant="outline" onClick={() => setOpen(true)}>Save to Project</Button>;

  return (
    <div className="flex items-center gap-2">
      <select value={selected} onChange={(e) => setSelected(e.target.value)}
        className="rounded-lg border px-2 py-1 text-xs h-7">
        <option value="">Select project...</option>
        {projects.map((p: any) => <option key={p.project_id} value={p.project_id}>{p.name}</option>)}
      </select>
      <Button size="sm" onClick={handleSave} disabled={!selected || saving}>
        {saving ? 'Saving...' : 'Save'}
      </Button>
    </div>
  );
}

function renderMarkdown(md: string): string {
  let html = md
    // Bold
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    // Headers
    .replace(/^### (.+)$/gm, '<h3 class="text-base font-semibold mt-4 mb-1">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-lg font-bold mt-5 mb-2">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold mt-6 mb-3">$1</h1>')
    // List items
    .replace(/^- (.+)$/gm, '<li class="ml-4 text-sm">$1</li>')
    .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 text-sm">$2</li>')
    // Table rows (simple)
    .replace(/^\|(.+)\|$/gm, (match: string) => {
      const cells = match.split('|').filter(c => c.trim());
      if (cells.every((c: string) => /^[-:]+$/.test(c.trim()))) return ''; // separator
      const tag = match.startsWith('|') && match.includes('---') ? '' : 'tr';
      return `<tr>${cells.map((c: string) => `<td class="border px-2 py-1 text-sm">${c.trim()}</td>`).join('')}</tr>`;
    })
    // Paragraphs (double newline)
    .replace(/\n\n/g, '</p><p class="text-sm leading-relaxed mb-2">')
    // Single newlines within paragraphs
    .replace(/\n/g, '<br/>');

  html = `<p class="text-sm leading-relaxed mb-2">${html}</p>`;
  // Wrap table rows
  html = html.replace(/(<tr>.+<\/tr>)+/g, '<table class="w-full border-collapse my-3"><tbody>$&</tbody></table>');
  // Wrap list items
  html = html.replace(/(<li[^>]*>.+<\/li>)+/g, '<ul class="my-2">$&</ul>');

  return html;
}
