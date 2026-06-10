/**
 * System Monitoring — real-time module health and performance from M8.
 *
 * WHAT: Fetches live metrics from M8 /admin/monitoring and /health endpoints.
 *       Auto-refreshes every 30 seconds. No mock data — all values come from
 *       the running system. When M8 is unreachable, shows last cached values
 *       with a "server unreachable" indicator.
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useTranslations } from 'next-intl';
import { getStats, getHealth } from '@/lib/api/monitoring';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Activity, BarChart3, Clock, CheckCircle2, XCircle, AlertCircle, RefreshCw, Loader2 } from 'lucide-react';

const MODULE_LABELS: Record<string, string> = {
  m1_doc_parsing: 'M1 Doc Parsing', m2_storage: 'M2 Storage', m3_retrieval: 'M3 Retrieval',
  m4_knowledge_graph: 'M4 Knowledge Graph', m5_qa_engine: 'M5 QA Engine', m8_api_gateway: 'M8 API Gateway',
};

function healthIcon(s: string) {
  if (s === 'ok' || s === 'healthy') return <CheckCircle2 className="h-4 w-4 text-green-500" />;
  if (s === 'degraded') return <AlertCircle className="h-4 w-4 text-yellow-500" />;
  return <XCircle className="h-4 w-4 text-red-500" />;
}

interface QAMetrics {
  total_queries?: number;
  avg_latency_ms?: number;
  by_mode?: Record<string, { count: number; avg_latency_ms: number }>;
}

export default function MonitoringPage() {
  const t = useTranslations();
  const [health, setHealth] = useState<Record<string, string> | null>(null);
  const [qaMetrics, setQaMetrics] = useState<QAMetrics | null>(null);
  const [uptime, setUptime] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true);
    setError('');
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

      // Fetch health + M5 query metrics in parallel from M8
      const [healthRes, qaRes] = await Promise.allSettled([
        fetch(`${baseUrl}/health`).then(r => r.ok ? r.json() : null),
        fetch(`${baseUrl}/admin/monitoring`).then(r => r.ok ? r.json() : null),
      ]);

      if (healthRes.status === 'fulfilled' && healthRes.value) {
        const h = healthRes.value;
        setUptime(h.uptime_seconds ?? 0);
        // Build module health map from health response
        const mods: Record<string, string> = {};
        if (h.modules) {
          for (const [k, v] of Object.entries(h.modules)) {
            mods[k] = String(v);
          }
        }
        setHealth(mods);
      }

      if (qaRes.status === 'fulfilled' && qaRes.value) {
        setQaMetrics(qaRes.value);
      }
    } catch {
      setError('Unable to reach M8 server on port 8000.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    load();
    intervalRef.current = setInterval(() => load(false), 30000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [load]);

  const modules = health ? Object.keys(health) : Object.keys(MODULE_LABELS);
  const uptimeHrs = (uptime / 3600).toFixed(1);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Connecting to M8...
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">{t('admin.monitoring.title')}</h1>
          <p className="text-sm text-muted-foreground">Auto-refreshes every 30s. Last update just now.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => load(true)} disabled={refreshing} className="gap-1.5">
          {refreshing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Refresh
        </Button>
      </div>

      {error && (
        <div className="mb-6 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive flex items-center gap-2">
          <XCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Module Health */}
      <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <Activity className="h-4 w-4 text-muted-foreground" /> Module Health
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-8">
        {modules.map((name) => {
          const s = health?.[name] ?? 'unknown';
          return (
            <Card key={name}>
              <CardContent className="flex flex-col items-center gap-2 p-4 text-center">
                {healthIcon(s)}
                <p className="text-xs font-medium">{MODULE_LABELS[name] || name}</p>
                <Badge variant="secondary" className="text-[10px]">{s === 'ok' || s === 'healthy' ? 'Healthy' : s === 'degraded' ? 'Degraded' : s}</Badge>
              </CardContent>
            </Card>
          );
        })}
        {modules.length === 0 && (
          <p className="col-span-full text-center text-sm text-muted-foreground py-4">
            No module health data. Is M8 running?
          </p>
        )}
      </div>

      {/* Metrics */}
      <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
        <BarChart3 className="h-4 w-4 text-muted-foreground" /> Performance Metrics
      </h2>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <MetricCard label="Total Queries" value={qaMetrics?.total_queries?.toLocaleString() ?? '—'} />
        <MetricCard label="Avg Latency" value={qaMetrics?.avg_latency_ms ? `${qaMetrics.avg_latency_ms.toFixed(0)} ms` : '—'} />
        <MetricCard label="Simple Mode" value={qaMetrics?.by_mode?.simple?.count?.toLocaleString() ?? '—'} sub={`${qaMetrics?.by_mode?.simple?.avg_latency_ms?.toFixed(0) ?? '—'} ms avg`} />
        <MetricCard label="Uptime" value={`${uptimeHrs} hrs`} />
      </div>

      {/* Query Mode Breakdown */}
      {qaMetrics?.by_mode && Object.keys(qaMetrics.by_mode).length > 0 && (
        <>
          <h2 className="text-sm font-semibold mb-3 flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" /> Query Mode Breakdown
          </h2>
          <Card className="mb-8"><CardContent className="p-0">
            <div className="divide-y">
              {Object.entries(qaMetrics.by_mode).map(([mode, info]) => (
                <div key={mode} className="flex items-center gap-4 px-4 py-3 text-sm">
                  <Badge variant="outline" className="text-xs capitalize">{mode}</Badge>
                  <span className="text-muted-foreground text-xs">{info.count} queries</span>
                  <span className="text-muted-foreground text-xs">{info.avg_latency_ms.toFixed(0)} ms avg</span>
                  <div className="flex-1" />
                  <div className="h-2 rounded-full bg-muted w-32 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary transition-all"
                      style={{ width: `${Math.min((info.count / (qaMetrics.total_queries || 1)) * 100, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent></Card>
        </>
      )}
    </div>
  );
}

function MetricCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Card><CardContent className="p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-bold mt-1">{value}</p>
      {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
    </CardContent></Card>
  );
}
