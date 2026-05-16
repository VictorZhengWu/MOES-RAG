/**
 * Document Management page — upload, list, filter, delete.
 * Fetches data from Mock Server (Phase 1) or real backend (Phase 2).
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useTranslations } from 'next-intl';
import type { DocumentRecord } from '@/types';
import { listDocuments, uploadDocument, deleteDocument } from '@/lib/api/documents';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Separator } from '@/components/ui/separator';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from '@/components/ui/dialog';
import { Upload, FileText, Search, Trash2, Loader2 } from 'lucide-react';

const DOMAINS = ['all', 'structure', 'machinery', 'piping', 'electrical', 'communication', 'automation', 'general'];
const SOCIETIES = ['all', 'DNV', 'ABS', 'CCS', 'LR', 'BV', 'IMO', 'IACS'];

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-500', deprecated: 'bg-yellow-500', error: 'bg-red-500',
  queued: 'bg-blue-300', processing: 'bg-blue-500', completed: 'bg-green-500', failed: 'bg-red-500',
};

export default function DocumentsPage() {
  const t = useTranslations();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [domainFilter, setDomainFilter] = useState('all');
  const [societyFilter, setSocietyFilter] = useState('all');
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listDocuments();
      setDocuments(res.documents);
    } catch { setDocuments([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  const filtered = documents.filter((d) => {
    const ms = !search || d.source_filename.toLowerCase().includes(search.toLowerCase()) ||
      (d.regulation_name || '').toLowerCase().includes(search.toLowerCase());
    const md = domainFilter === 'all' || d.domain === domainFilter;
    const ms2 = societyFilter === 'all' || d.classification_society === societyFilter;
    return ms && md && ms2;
  });

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg('');
    try {
      await uploadDocument({ file_name: file.name, domain: 'general' });
      setUploadMsg('Upload successful. Parsing started.');
      setTimeout(() => { setUploadMsg(''); fetchDocuments(); }, 1500);
    } catch {
      setUploadMsg('Upload failed.');
    } finally { setUploading(false); }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    await deleteDocument(deleteTarget);
    setDocuments((prev) => prev.filter((d) => d.doc_id !== deleteTarget));
    setDeleteTarget(null);
  };

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="text-xl font-bold">{t('admin.documents.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('admin.documents.subtitle')}</p>
        </div>
      </div>

      {/* Upload area */}
      <Card className="mb-6 border-dashed">
        <CardContent className="flex flex-col items-center justify-center py-8">
          <Upload className="h-8 w-8 text-muted-foreground mb-2" />
          <p className="text-sm font-medium">{t('admin.documents.upload.dragDrop')}</p>
          <p className="text-xs text-muted-foreground mt-1 mb-4">{t('admin.documents.upload.supportedFormats')}</p>
          <input ref={fileInputRef} type="file" className="hidden" onChange={handleUpload} disabled={uploading} />
          <Button variant="outline" size="sm" disabled={uploading} onClick={() => fileInputRef.current?.click()}>
            {uploading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
            {uploading ? t('admin.documents.upload.uploading') : 'Browse Files'}
          </Button>
          {uploadMsg && <p className="text-xs text-primary mt-2">{uploadMsg}</p>}
        </CardContent>
      </Card>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder={t('common.search') + '...'} className="pl-8" />
        </div>
        <select value={societyFilter} onChange={(e) => setSocietyFilter(e.target.value)} className="rounded-lg border bg-background px-3 py-2 text-sm">
          {SOCIETIES.map((s) => <option key={s} value={s}>{s === 'all' ? 'All Societies' : s}</option>)}
        </select>
        <select value={domainFilter} onChange={(e) => setDomainFilter(e.target.value)} className="rounded-lg border bg-background px-3 py-2 text-sm">
          {DOMAINS.map((d) => <option key={d} value={d}>{d === 'all' ? 'All Domains' : d}</option>)}
        </select>
      </div>

      {/* Document Table */}
      {loading ? (
        <p className="text-sm text-muted-foreground py-8 text-center">{t('common.loading')}</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">{t('common.noResults')}</p>
      ) : (
        <div className="rounded-lg border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('admin.documents.table.filename')}</TableHead>
                <TableHead>{t('admin.documents.table.society')}</TableHead>
                <TableHead>{t('admin.documents.table.domain')}</TableHead>
                <TableHead>{t('admin.documents.table.version')}</TableHead>
                <TableHead className="text-right">{t('admin.documents.table.chunks')}</TableHead>
                <TableHead>{t('admin.documents.table.status')}</TableHead>
                <TableHead className="text-right">{t('admin.documents.table.actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((doc) => (
                <TableRow key={doc.doc_id}>
                  <TableCell className="font-medium text-sm max-w-[280px] truncate">{doc.source_filename}</TableCell>
                  <TableCell className="text-sm">{doc.classification_society || '—'}</TableCell>
                  <TableCell className="text-sm">{doc.domain}</TableCell>
                  <TableCell className="text-sm">{doc.version_year || '—'}</TableCell>
                  <TableCell className="text-sm text-right">{doc.chunks_count}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="gap-1.5 text-xs">
                      <span className={`h-1.5 w-1.5 rounded-full ${STATUS_COLORS[doc.status] || 'bg-gray-400'}`} />
                      {t(`admin.documents.status.${doc.status}` as any) || doc.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setDeleteTarget(doc.doc_id)} title={t('common.delete')}>
                      <Trash2 className="h-4 w-4 text-muted-foreground" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Delete confirmation dialog */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('admin.documents.actions.delete')}</DialogTitle>
            <DialogDescription>{t('admin.documents.actions.deleteConfirm')}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>{t('common.cancel')}</Button>
            <Button variant="destructive" onClick={handleDelete}>{t('common.delete')}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
