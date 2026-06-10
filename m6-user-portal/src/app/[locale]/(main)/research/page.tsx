/**
 * Deep Research page — multi-step research with SSE progress.
 * Phase 4-A: Planner → Retrieval → Analysis → Report
 */
'use client';

import { useState, useRef, useCallback } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Loader2, Brain, FileText, Globe, CheckCircle2, AlertCircle } from 'lucide-react';

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
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

    try {
      const res = await fetch(`${baseUrl}/api/v1/agent/research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ query: query.trim(), stream: true }),
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
                setReport, setDone, setError);
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
            <Button onClick={handleStart} disabled={!query.trim() || running} className="gap-2">
              <Brain className="h-4 w-4" />
              Start Research
            </Button>
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
            <div dangerouslySetInnerHTML={{ __html: renderMarkdown(report) }} />
          </CardContent>
        </Card>
      )}

      {/* Done state */}
      {done && (
        <div className="mt-4 flex items-center gap-2 text-sm text-muted-foreground">
          <CheckCircle2 className="h-4 w-4 text-green-500" />
          Research complete
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
) {
  if (data.phase) setPhase(data.phase);
  if (data.progress !== undefined) setProgress(data.progress);
  if (data.message) setMessage(data.message);
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
