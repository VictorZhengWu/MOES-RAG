/**
 * Admin Dashboard — system overview with stats and module health.
 * Data fetched from Mock Server (Phase 1) or real M5 backend (Phase 2).
 */

'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import { getStats, getHealth } from '@/lib/api/monitoring';
import type { SystemStats, ModuleHealth } from '@/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { FileText, Grid3X3, Users, MessageSquare, HardDrive, Gauge, Activity } from 'lucide-react';

function healthColor(status: string): string {
  if (status === 'ok') return 'bg-green-500';
  if (status === 'degraded') return 'bg-yellow-500';
  return 'bg-red-500';
}

export default function DashboardPage() {
  const t = useTranslations();
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [modules, setModules] = useState<ModuleHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getStats(), getHealth()])
      .then(([s, h]) => { setStats(s); setModules(h.modules); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="p-8 text-sm text-muted-foreground">{t('common.loading')}</div>;

  const statCards = [
    { icon: FileText, label: t('admin.dashboard.totalDocuments'), value: stats?.total_documents ?? 0 },
    { icon: Grid3X3, label: t('admin.dashboard.totalChunks'), value: stats?.total_chunks ?? 0 },
    { icon: Users, label: t('admin.dashboard.totalUsers'), value: stats?.total_users ?? 0 },
    { icon: MessageSquare, label: t('admin.dashboard.totalConversations'), value: stats?.total_conversations ?? 0 },
  ];

  const gb = ((stats?.storage_size_bytes ?? 0) / 1e9).toFixed(1);
  const moduleNames = modules ? Object.keys(modules) : [];

  return (
    <div className="p-8">
      <h1 className="text-xl font-bold">{t('admin.dashboard.title')}</h1>
      <p className="text-sm text-muted-foreground mt-1 mb-8">{t('admin.dashboard.subtitle')}</p>

      {/* Stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {statCards.map((c) => (
          <Card key={c.label}>
            <CardContent className="flex items-center gap-4 p-4">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
                <c.icon className="h-5 w-5 text-primary" />
              </div>
              <div>
                <p className="text-2xl font-bold">{c.value.toLocaleString()}</p>
                <p className="text-xs text-muted-foreground">{c.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Storage */}
        <Card>
          <CardHeader className="flex flex-row items-center gap-2 pb-2">
            <HardDrive className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">{t('admin.dashboard.storageUsed')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold mb-2">{gb} GB</p>
            <Progress value={Math.min((stats?.storage_size_bytes ?? 0) / 5e9 * 100, 100)} className="h-2" />
            <p className="text-xs text-muted-foreground mt-1">of 5 GB limit</p>
          </CardContent>
        </Card>

        {/* Latency */}
        <Card>
          <CardHeader className="flex flex-row items-center gap-2 pb-2">
            <Gauge className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">{t('admin.dashboard.avgLatency')}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold">{stats?.avg_retrieval_latency_ms?.toFixed(1) ?? '—'} ms</p>
          </CardContent>
        </Card>
      </div>

      {/* Module Health */}
      <Card className="mt-6">
        <CardHeader className="flex flex-row items-center gap-2 pb-2">
          <Activity className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">Module Health</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            {moduleNames.map((name) => {
              const status = modules?.[name as keyof ModuleHealth] ?? 'down';
              return (
                <Badge key={name} variant="outline" className="gap-2 px-3 py-2 text-xs">
                  <span className={`h-2 w-2 rounded-full ${healthColor(status)}`} />
                  {name.replace(/_/g, ' ').toUpperCase()}
                </Badge>
              );
            })}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
