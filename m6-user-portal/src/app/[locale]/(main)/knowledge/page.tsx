/**
 * Knowledge Base browser page.
 *
 * Fetches the list of ingested documents from the API and displays
 * them with filtering by classification society, domain, and year.
 * Clicking a document could eventually open a detail view.
 *
 * WHY: Users need to know what knowledge is available before asking
 * questions. This page lists all indexed documents from the Mock
 * Server (Phase 1) or real M5 backend (Phase 2).
 */

'use client';

import { useEffect, useState } from 'react';
import { useTranslations } from 'next-intl';
import type { DocumentInfo } from '@/types';
import { apiGet } from '@/lib/api/client';
import { Input } from '@/components/ui/input';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Search, FileText } from 'lucide-react';

const DOMAINS = ['all', 'structure', 'machinery', 'piping', 'electrical', 'communication', 'automation', 'general'];
const SOCIETIES = ['all', 'DNV', 'ABS', 'CCS', 'LR', 'BV', 'IMO', 'IACS'];

export default function KnowledgePage() {
  const t = useTranslations();
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [domainFilter, setDomainFilter] = useState('all');
  const [societyFilter, setSocietyFilter] = useState('all');

  useEffect(() => {
    apiGet<{ documents: DocumentInfo[]; total: number }>('/api/v1/admin/documents')
      .then((res) => setDocuments(res.documents))
      .catch(() => setDocuments([]))
      .finally(() => setLoading(false));
  }, []);

  const filtered = documents.filter((d) => {
    const matchesSearch =
      !search ||
      d.source_filename.toLowerCase().includes(search.toLowerCase()) ||
      (d.regulation_name || '').toLowerCase().includes(search.toLowerCase());
    const matchesDomain = domainFilter === 'all' || d.domain === domainFilter;
    const matchesSociety =
      societyFilter === 'all' ||
      d.classification_society === societyFilter;
    return matchesSearch && matchesDomain && matchesSociety;
  });

  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-1">
        <FileText className="h-5 w-5 text-muted-foreground" />
        <h1 className="text-xl font-bold">{t('knowledge.title')}</h1>
      </div>
      <p className="text-sm text-muted-foreground">
        {t('knowledge.subtitle')}
      </p>

      {/* Search + Filters */}
      <div className="mt-6 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder={t('knowledge.search')}
            className="pl-8"
          />
        </div>
        <select
          value={societyFilter}
          onChange={(e) => setSocietyFilter(e.target.value)}
          className="rounded-lg border bg-background px-3 py-2 text-sm"
        >
          {SOCIETIES.map((s) => (
            <option key={s} value={s}>
              {s === 'all' ? t('knowledge.filter.all') + ' ' + t('knowledge.filter.society') : s}
            </option>
          ))}
        </select>
        <select
          value={domainFilter}
          onChange={(e) => setDomainFilter(e.target.value)}
          className="rounded-lg border bg-background px-3 py-2 text-sm"
        >
          {DOMAINS.map((d) => (
            <option key={d} value={d}>
              {d === 'all' ? t('knowledge.filter.all') + ' ' + t('knowledge.filter.domain') : d}
            </option>
          ))}
        </select>
      </div>

      {/* Document list */}
      <ScrollArea className="mt-4 h-[calc(100vh-280px)]">
        {loading ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            {t('common.loading')}
          </p>
        ) : filtered.length === 0 ? (
          <p className="py-12 text-center text-sm text-muted-foreground">
            {t('knowledge.empty')}
          </p>
        ) : (
          <div className="space-y-2">
            {filtered.map((doc) => (
              <Card key={doc.doc_id}>
                <CardContent className="flex items-center justify-between p-4">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-sm truncate">
                      {doc.source_filename}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {doc.classification_society ?? '—'} &middot;{' '}
                      {doc.regulation_name ?? '—'} &middot; v
                      {doc.version_year ?? '—'}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 ml-4 shrink-0">
                    <Badge variant="outline" className="text-xs">
                      {doc.domain}
                    </Badge>
                    <Badge variant="secondary" className="text-xs">
                      {doc.chunks_count} {t('knowledge.table.chunks')}
                    </Badge>
                    <Badge
                      variant={
                        doc.status === 'active'
                          ? 'default'
                          : doc.status === 'deprecated'
                            ? 'secondary'
                            : 'destructive'
                      }
                      className="text-xs"
                    >
                      {t(`knowledge.status.${doc.status}` as any) || doc.status}
                    </Badge>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
