/**
 * System Monitoring — module health, performance metrics, logs.
 * Data from Mock Server (Phase 1) or real M5 backend (Phase 2).
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import type { SystemStats, ModuleHealth } from '@/types';
import { getStats, getHealth } from '@/lib/api/monitoring';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Activity, BarChart3, Server, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';

const MOCK_LOGS = [
  { level: 'INFO', timestamp: '2026-05-17 14:32:01', module: 'm3_retrieval', message: 'Search completed in 245ms, 20 results returned' },
  { level: 'INFO', timestamp: '2026-05-17 14:31:58', module: 'm1_doc_parsing', message: 'Document parsed: 312 chunks' },
  { level: 'WARN', timestamp: '2026-05-17 14:31:45', module: 'm5_qa_engine', message: 'LLM latency 3.2s exceeds threshold 2.0s' },
  { level: 'INFO', timestamp: '2026-05-17 14:30:12', module: 'm2_storage', message: 'Vector index rebuilt: 12850 vectors' },
  { level: 'ERROR', timestamp: '2026-05-17 14:28:03', module: 'm8_api_gateway', message: 'Rate limit exceeded for API key — 429' },
  { level: 'INFO', timestamp: '2026-05-17 14:25:00', module: 'm4_knowledge_graph', message: 'Entity extraction: 156 entities, 89 relations' },
];

const LOG_COLORS: Record<string, string> = { INFO: 'bg-blue-500', WARN: 'bg-yellow-500', ERROR: 'bg-red-500' };

const MODULE_LABELS: Record<string, string> = {
  m1_doc_parsing: 'M1 Doc Parsing', m2_storage: 'M2 Storage', m3_retrieval: 'M3 Retrieval',
  m4_knowledge_graph: 'M4 Knowledge Graph', m5_qa_engine: 'M5 QA Engine', m8_api_gateway: 'M8 API Gateway',
};

function healthIcon(s: string) {
  if (s === 'ok') return <CheckCircle2 className="h-4 w-4 text-green-500" />;
  if (s === 'degraded') return <AlertCircle className="h-4 w-4 text-yellow-500" />;
  return <XCircle className="h-4 w-4 text-red-500" />;
}

export default function MonitoringPage() {
  const t = useTranslations();
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [health, setHealth] = useState<{ status: string; modules: ModuleHealth; uptime_seconds: number } | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try { const [s, h] = await Promise.all([getStats(), getHealth()]); setStats(s); setHealth(h); }
    catch { /* use defaults */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <div className="p-8 text-sm text-muted-foreground">Loading...</div>;

  const modules = health?.modules ? Object.keys(health.modules) : [];
  const uptimeHrs = ((health?.uptime_seconds ?? 0) / 3600).toFixed(1);

  return (
    <div className="p-8">
      <h1 className="text-xl font-bold mb-1">{t('admin.monitoring.title')}</h1>
      <p className="text-sm text-muted-foreground mb-6">{t('admin.monitoring.subtitle')}</p>

      {/* Module Health */}
      <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Activity className="h-4 w-4 text-muted-foreground" /> Module Health
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
        {modules.map((name) => {
          const s = health?.modules[name as keyof ModuleHealth] ?? 'down';
          return (
            <Card key={name}>
              <CardContent className="flex flex-col items-center gap-2 p-4 text-center">
                {healthIcon(s)}
                <p className="text-xs font-medium">{MODULE_LABELS[name] || name}</p>
                <Badge variant="secondary" className="text-[10px]">{s === 'ok' ? 'Healthy' : s === 'degraded' ? 'Degraded' : 'Down'}</Badge>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Metrics */}
      <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-muted-foreground" /> Performance Metrics
      </h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {[
          { label: 'Avg Retrieval Latency', val: `${stats?.avg_retrieval_latency_ms?.toFixed(1) ?? '—'} ms` },
          { label: 'Total Documents', val: stats?.total_documents?.toLocaleString() ?? '—' },
          { label: 'Total Chunks', val: stats?.total_chunks?.toLocaleString() ?? '—' },
          { label: 'Uptime', val: `${uptimeHrs} hrs` },
        ].map((m) => (
          <Card key={m.label}><CardContent className="p-4">
            <p className="text-xs text-muted-foreground">{m.label}</p>
            <p className="text-2xl font-bold mt-1">{m.val}</p>
          </CardContent></Card>
        ))}
      </div>

      {/* Recent Logs */}
      <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Server className="h-4 w-4 text-muted-foreground" /> Recent Logs
      </h2>
      <Card><CardContent className="p-0">
        <div className="divide-y">
          {MOCK_LOGS.map((log, i) => (
            <div key={i} className="flex items-start gap-3 px-4 py-2.5 text-sm">
              <Badge className={`text-[10px] shrink-0 mt-0.5 text-white ${LOG_COLORS[log.level]}`}>{log.level}</Badge>
              <span className="text-xs text-muted-foreground shrink-0 w-[140px]">{log.timestamp}</span>
              <Badge variant="outline" className="text-[10px] shrink-0">{MODULE_LABELS[log.module] || log.module}</Badge>
              <span className="text-xs truncate">{log.message}</span>
            </div>
          ))}
        </div>
      </CardContent></Card>
    </div>
  );
}
