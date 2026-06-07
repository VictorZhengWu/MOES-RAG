/**
 * System Configuration — all runtime settings in one page.
 *
 * Tabs: Features | SMTP | Storage (future: Retrieval, Parsing)
 *
 * WHAT: Replaces deploy.yaml editing. Admins configure every system
 *       parameter through UI. Changes hot-reload into running services.
 */
'use client';

import { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Badge } from '@/components/ui/badge';
import { Loader2, Settings, Mail, ToggleLeft } from 'lucide-react';
import { getFeatures, updateFeatures, getSMTPConfig, updateSMTPConfig } from '@/lib/api/llm-config';

export default function SystemConfigPage() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [status, setStatus] = useState<Record<string, string>>({});

  // ── Features ──
  const [features, setFeatures] = useState({
    feature_web_search: true, feature_billing: false,
    feature_deep_research: false, feature_multi_tenant: false,
  });

  // ── SMTP ──
  const [smtp, setSMTP] = useState({ host: 'smtp.gmail.com', port: '587', user: '', password: '' });

  useEffect(() => {
    (async () => {
      try {
        const [f, s] = await Promise.all([getFeatures(), getSMTPConfig()]);
        if (f.feature_web_search !== undefined) setFeatures({
          feature_web_search: f.feature_web_search === 'true',
          feature_billing: f.feature_billing === 'true',
          feature_deep_research: f.feature_deep_research === 'true',
          feature_multi_tenant: f.feature_multi_tenant === 'true',
        });
        if (s.host) setSMTP({ host: s.host, port: s.port || '587', user: s.user || '', password: s.password || '' });
      } catch { /* M8 may not be running */ }
      setLoading(false);
    })();
  }, []);

  const saveFeatures = async () => {
    setSaving('features');
    try {
      await updateFeatures(features);
      setStatus((s) => ({ ...s, features: 'saved' }));
    } catch { setStatus((s) => ({ ...s, features: 'error' })); }
    setSaving(null);
  };

  const saveSMTP = async () => {
    if (!smtp.host.trim()) { setStatus((s) => ({ ...s, smtp: 'Host required' })); return; }
    const portNum = parseInt(smtp.port);
    if (isNaN(portNum) || portNum < 1 || portNum > 65535) { setStatus((s) => ({ ...s, smtp: 'Invalid port (1-65535)' })); return; }
    setSaving('smtp');
    try {
      await updateSMTPConfig({ host: smtp.host.trim(), port: portNum, user: smtp.user.trim(), password: smtp.password });
      setStatus((s) => ({ ...s, smtp: 'saved' }));
    } catch { setStatus((s) => ({ ...s, smtp: 'error' })); }
    setSaving(null);
  };

  if (loading) return <div className="p-8 text-sm text-muted-foreground">Loading...</div>;

  return (
    <div className="p-8">
      <h1 className="text-xl font-bold mb-1">System Configuration</h1>
      <p className="text-sm text-muted-foreground mb-6">All settings are hot-reloaded — no restart needed.</p>

      <Tabs defaultValue="features">
        <TabsList className="mb-4">
          <TabsTrigger value="features" className="gap-1.5"><ToggleLeft className="h-3.5 w-3.5" /> Features</TabsTrigger>
          <TabsTrigger value="smtp" className="gap-1.5"><Mail className="h-3.5 w-3.5" /> SMTP</TabsTrigger>
        </TabsList>

        {/* ── Features Tab ─────────────────────────────────── */}
        <TabsContent value="features">
          <Card>
            <CardHeader><CardTitle className="text-base">Feature Flags</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {Object.entries(features).map(([key, val]) => (
                <div key={key} className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}</p>
                    <p className="text-xs text-muted-foreground">
                      {key === 'feature_web_search' && 'Enables live web search in Q&A responses'}
                      {key === 'feature_billing' && 'Enables Stripe billing (SaaS mode only)'}
                      {key === 'feature_deep_research' && 'Enables multi-step research agent'}
                      {key === 'feature_multi_tenant' && 'Enables tenant isolation (SaaS mode)'}
                    </p>
                  </div>
                  <button
                    onClick={() => setFeatures((f) => ({ ...f, [key]: !val }))}
                    className={`w-10 h-6 rounded-full transition-colors ${val ? 'bg-green-500' : 'bg-gray-300'}`}
                  >
                    <div className={`w-5 h-5 bg-white rounded-full shadow transition-transform ${val ? 'translate-x-[18px]' : 'translate-x-[2px]'}`} />
                  </button>
                </div>
              ))}
              <div className="flex items-center gap-2 pt-2">
                <Button size="sm" onClick={saveFeatures} disabled={saving === 'features'}>
                  {saving === 'features' && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />} Save
                </Button>
                {status.features && <Badge variant={status.features === 'saved' ? 'default' : 'destructive'} className="text-[10px]">{status.features === 'saved' ? 'Saved' : 'Failed'}</Badge>}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ── SMTP Tab ──────────────────────────────────────── */}
        <TabsContent value="smtp">
          <Card>
            <CardHeader><CardTitle className="text-base">SMTP Email Settings</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Host</label>
                  <Input value={smtp.host} onChange={(e) => setSMTP({ ...smtp, host: e.target.value })} placeholder="smtp.gmail.com" className="mt-1 h-9 text-sm" />
                </div>
                <div>
                  <label className="text-xs font-medium text-muted-foreground">Port</label>
                  <Input value={smtp.port} onChange={(e) => setSMTP({ ...smtp, port: e.target.value })} placeholder="587" className="mt-1 h-9 text-sm" />
                </div>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Username (email)</label>
                <Input value={smtp.user} onChange={(e) => setSMTP({ ...smtp, user: e.target.value })} placeholder="noreply@example.com" className="mt-1 h-9 text-sm" />
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Password</label>
                <Input type="password" value={smtp.password} onChange={(e) => setSMTP({ ...smtp, password: e.target.value })} placeholder="App password (not your main password)" className="mt-1 h-9 text-sm" />
              </div>
              <div className="flex items-center gap-2 pt-1">
                <Button size="sm" onClick={saveSMTP} disabled={saving === 'smtp'}>
                  {saving === 'smtp' && <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />} Save
                </Button>
                {status.smtp && <Badge variant={status.smtp === 'saved' ? 'default' : 'destructive'} className="text-[10px]">{status.smtp === 'saved' ? 'Saved' : status.smtp}</Badge>}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
