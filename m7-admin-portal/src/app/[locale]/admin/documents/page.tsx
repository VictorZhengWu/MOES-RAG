/**
 * Document Management — upload with filename parsing.
 *
 * Flow:
 * 1. Drop/browse files → filenames parsed client-side
 * 2. Preview parsed metadata in a table
 * 3. User adds domain + language per file
 * 4. Confirm → uploaded to Mock Server (Phase 1) / real backend (Phase 2)
 * 5. Document list below with filters and status management
 */

'use client';

import { useEffect, useState, useCallback, useRef } from 'react';
import { useTranslations } from 'next-intl';
import type { DocumentRecord } from '@/types';
import { listDocuments, uploadDocument, deleteDocument } from '@/lib/api/documents';
import { parseFilename, batchParse, formatVersion, SUPPORTED_FORMATS_DISPLAY, MAX_FILE_SIZE, type ParsedDocument } from '@/lib/filename-parser';
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Upload, FileText, Search, Trash2, Loader2, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';

const DOMAINS = ['structure', 'machinery', 'piping', 'electrical', 'communication', 'automation', 'general'];
const SOCIETIES = ['all', 'DNV', 'ABS', 'CCS', 'LR', 'BV', 'IMO', 'IACS'];

interface PendingFile extends ParsedDocument {
  /** Original File object for upload */
  file: File;
  /** User-selected domain */
  domain: string;
  /** Document language */
  language: string;
}

export default function DocumentsPage() {
  const t = useTranslations();
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [societyFilter, setSocietyFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortField, setSortField] = useState<string>('source_filename');
  const [sortAsc, setSortAsc] = useState(true);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  // Upload state
  const [pendingFiles, setPendingFiles] = useState<PendingFile[]>([]);

  // Backend availability (fetched from M8 on mount)
  const [backendsAvailable, setBackendsAvailable] = useState<Record<string, boolean>>({docling: true});
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');
  const [uploadProgress, setUploadProgress] = useState({ current: 0, total: 0, filename: '' });
  const [uploadElapsed, setUploadElapsed] = useState(0);
  const uploadTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [invalidDialogOpen, setInvalidDialogOpen] = useState(false);
  const [invalidFilenames, setInvalidFilenames] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    try { const res = await listDocuments(); setDocuments(res.documents); }
    catch { setDocuments([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchDocuments(); }, [fetchDocuments]);

  // ── File processing ──────────────────────────────────────────────
  const processFiles = useCallback((fileList: FileList | null) => {
    if (!fileList) return;
    const files = Array.from(fileList);
    const names = files.map((f) => f.name);
    const { valid, invalid } = batchParse(names);

    // Collect error messages for invalid files (format + pattern errors)
    const errors: string[] = [];
    for (const inv of invalid) {
      errors.push(`${inv.raw}: ${inv.error}`);
    }

    const pending: PendingFile[] = [];
    for (const parsed of valid) {
      const file = files.find((f) => f.name === parsed.raw || f.name.startsWith(parsed.raw))!;

      // Check file size
      if (file.size > MAX_FILE_SIZE) {
        errors.push(`${file.name}: File too large (${(file.size / 1024 / 1024).toFixed(1)}MB). Max ${MAX_FILE_SIZE / 1024 / 1024}MB.`);
        continue;
      }

      // Check duplicate against existing documents
      const dup = documents.find((d) => d.source_filename === file.name);
      if (dup) {
        errors.push(`${file.name}: A document with this name already exists (status: ${dup.status}).`);
        continue;
      }

      pending.push({ ...parsed, file, domain: 'general', language: 'en' });
    }

    // Show errors in dialog
    if (errors.length > 0) {
      setInvalidFilenames(errors);
      setInvalidDialogOpen(true);
    }

    if (pending.length > 0) setPendingFiles((prev) => [...prev, ...pending]);
  }, [documents]);

  const removePending = (index: number) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const updatePendingField = (index: number, field: 'domain' | 'language', value: string) => {
    setPendingFiles((prev) =>
      prev.map((p, i) => (i === index ? { ...p, [field]: value } : p)),
    );
  };

  // ── Upload ────────────────────────────────────────────────────────
  const handleUploadAll = async () => {
    if (pendingFiles.length === 0) return;
    setUploading(true);
    setUploadMsg('');
    setUploadElapsed(0);
    setUploadProgress({ current: 0, total: pendingFiles.length, filename: '' });
    const startTime = Date.now();
    uploadTimerRef.current = setInterval(() => setUploadElapsed(Math.floor((Date.now() - startTime) / 1000)), 1000);
    const results: string[] = [];
    let success = 0;
    let fail = 0;

    for (let i = 0; i < pendingFiles.length; i++) {
      const pf = pendingFiles[i];
      setUploadProgress({ current: i + 1, total: pendingFiles.length, filename: pf.file.name });
      try {
        await uploadDocument({
          file_name: pf.file.name,
          classification_society: pf.society,
          regulation_name: pf.name,
          version_year: parseInt(pf.version?.substring(0, 4) || '0'),
          domain: pf.domain,
          language: pf.language,
          custom_tags: {
            category: pf.category,
            section: pf.section,
            version_full: pf.version,
          },
        });
        success++;
        results.push(`✓ ${pf.file.name}`);
      } catch (err: unknown) {
        fail++;
        const msg = err instanceof Error ? err.message : 'Unknown error';
        results.push(`✗ ${pf.file.name} — ${msg}`);
      }
    }

    setUploadMsg(results.join('\n'));
    if (success > 0) {
      setPendingFiles([]);
      setTimeout(() => { setUploadMsg(''); fetchDocuments(); }, 4000);
    }
    if (uploadTimerRef.current) { clearInterval(uploadTimerRef.current); uploadTimerRef.current = null; }
    setUploading(false);
  };

  // ── Delete ────────────────────────────────────────────────────────
  const handleDelete = async () => {
    if (!deleteTarget) return;
    await deleteDocument(deleteTarget);
    setDocuments((prev) => prev.filter((d) => d.doc_id !== deleteTarget));
    setDeleteTarget(null);
  };

  // ── Filters ───────────────────────────────────────────────────────
  const filtered = documents
    .filter((d) => {
      const ms = !search || d.source_filename.toLowerCase().includes(search.toLowerCase());
      const ms2 = societyFilter === 'all' || d.classification_society === societyFilter;
      const ms3 = statusFilter === 'all' || d.status === statusFilter;
      return ms && ms2 && ms3;
    })
    .sort((a, b) => {
      const va = (a as any)[sortField] ?? '';
      const vb = (b as any)[sortField] ?? '';
      const cmp = String(va).localeCompare(String(vb), undefined, { numeric: true });
      return sortAsc ? cmp : -cmp;
    });
  const handleSort = (field: string) => {
    if (sortField === field) setSortAsc(!sortAsc);
    else { setSortField(field); setSortAsc(true); }
  };
  const sortIcon = (field: string) =>
    sortField === field ? (sortAsc ? ' ▲' : ' ▼') : '';

  const STATUS_COLORS: Record<string, string> = {
    active: 'bg-green-500', deprecated: 'bg-yellow-500', error: 'bg-red-500',
  };

  return (
    <div className="p-8">
      <h1 className="text-xl font-bold mb-1">{t('admin.documents.title')}</h1>
      <p className="text-sm text-muted-foreground mb-6">{t('admin.documents.subtitle')}</p>

      {/* ── Upload Area ──────────────────────────────────────────── */}
      <div className="relative mb-6">
        <Card className={`border-2 border-dashed transition-colors ${isDragOver ? 'border-primary bg-primary/5' : ''}`}>
          <CardContent
            className="flex flex-col items-center justify-center py-10 cursor-pointer"
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragOver(true); }}
            onDragLeave={(e) => { e.preventDefault(); e.stopPropagation(); setIsDragOver(false); }}
            onDrop={(e) => {
              e.preventDefault(); e.stopPropagation();
              setIsDragOver(false);
              processFiles(e.dataTransfer.files);
            }}
          >
            <Upload className={`h-10 w-10 mb-3 ${isDragOver ? 'text-primary' : 'text-muted-foreground'}`} />
            <p className={`text-sm font-medium ${isDragOver ? 'text-primary' : ''}`}>
              {isDragOver ? 'Release to add files' : 'Drop files here or click to browse'}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Expected: [Society][Category][Section][Name][YYYYMM].ext
            </p>
            <p className="text-xs text-muted-foreground">
              Supported: {SUPPORTED_FORMATS_DISPLAY}
            </p>
            <p className="text-xs text-muted-foreground">
              Example: [DNV][RU-SHIP][Pt.1-Ch.1][General regulations][202507].pdf
            </p>
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              multiple
              onChange={(e) => { processFiles(e.target.files); e.target.value = ''; }}
            />
          </CardContent>
        </Card>

        {/* Drag-over overlay with blur */}
        {isDragOver && (
          <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-background/60 backdrop-blur-sm pointer-events-none">
            <div className="flex flex-col items-center gap-2 rounded-2xl border-2 border-primary/50 bg-background/90 px-12 py-8 shadow-2xl">
              <Upload className="h-12 w-12 text-primary" />
              <p className="text-lg font-semibold">Add documents</p>
              <p className="text-sm text-muted-foreground">Drop any file here to add it</p>
            </div>
          </div>
        )}
      </div>

      {/* ── Pending files preview ────────────────────────────────── */}
      {pendingFiles.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold">
              Pending Upload ({pendingFiles.length} file{pendingFiles.length > 1 ? 's' : ''})
            </h2>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setPendingFiles([])} disabled={uploading}>
                Clear All
              </Button>
              <Button size="sm" onClick={handleUploadAll} disabled={uploading}>
                {uploading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {uploading ? 'Uploading...' : `Upload ${pendingFiles.length} File${pendingFiles.length > 1 ? 's' : ''}`}
              </Button>
            </div>
            {uploading && (
              <div className="mt-2">
                <div className="flex justify-between text-xs text-muted-foreground mb-1">
                  <span>Parsing: {uploadProgress.filename}</span>
                  <span>{uploadProgress.current}/{uploadProgress.total} · {uploadElapsed}s</span>
                </div>
                <div className="w-full h-1.5 bg-muted rounded-full overflow-hidden">
                  <div className="h-full bg-primary rounded-full transition-all duration-300"
                    style={{ width: `${(uploadProgress.current / uploadProgress.total) * 100}%` }} />
                </div>
              </div>
            )}
            {/* Backend selector + timeout */}
            <div className="flex items-center gap-3 mt-3 text-xs text-muted-foreground">
              <span>Engine:</span>
              <select className="rounded border bg-background px-2 py-1 text-xs">
                <option>Docling</option>
                <option>Marker (pip install marker-pdf)</option>
                <option>MinerU (pip install magic-pdf)</option>
              </select>
              <span>Timeout:</span>
              <select className="rounded border bg-background px-2 py-1 text-xs" defaultValue="120">
                <option value="60">60s</option>
                <option value="120">120s</option>
                <option value="300">300s</option>
                <option value="600">600s</option>
              </select>
            </div>
          </div>

          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[30px]">#</TableHead>
                  <TableHead>Filename</TableHead>
                  <TableHead>Society</TableHead>
                  <TableHead>Category</TableHead>
                  <TableHead>Section</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>Version</TableHead>
                  <TableHead>Domain</TableHead>
                  <TableHead>Lang</TableHead>
                  <TableHead className="w-[30px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pendingFiles.map((pf, i) => (
                  <TableRow key={i}>
                    <TableCell className="text-xs text-muted-foreground">{i + 1}</TableCell>
                    <TableCell className="text-xs font-medium max-w-[180px] truncate">{pf.file.name}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-xs">{pf.society}</Badge>
                    </TableCell>
                    <TableCell className="text-xs">{pf.category}</TableCell>
                    <TableCell className="text-xs font-mono">{pf.section}</TableCell>
                    <TableCell className="text-xs max-w-[160px] truncate">{pf.name}</TableCell>
                    <TableCell className="text-xs">{formatVersion(pf.version)}</TableCell>
                    <TableCell>
                      <select
                        value={pf.domain}
                        onChange={(e) => updatePendingField(i, 'domain', e.target.value)}
                        className="text-xs rounded border bg-background px-1 py-0.5"
                      >
                        {DOMAINS.map((d) => <option key={d} value={d}>{d}</option>)}
                      </select>
                    </TableCell>
                    <TableCell>
                      <select
                        value={pf.language}
                        onChange={(e) => updatePendingField(i, 'language', e.target.value)}
                        className="text-xs rounded border bg-background px-1 py-0.5"
                      >
                        <option value="en">EN</option>
                        <option value="zh">ZH</option>
                        <option value="ko">KO</option>
                        <option value="ja">JA</option>
                        <option value="no">NO</option>
                      </select>
                    </TableCell>
                    <TableCell>
                      <Button variant="ghost" size="icon" className="h-6 w-6" onClick={() => removePending(i)}>
                        <XCircle className="h-3.5 w-3.5 text-muted-foreground" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {uploadMsg && (
            <p className={`text-xs mt-2 ${uploadMsg.includes('failed') || uploadMsg.includes('Skipped') ? 'text-yellow-600' : 'text-green-600'}`}>
              {uploadMsg}
            </p>
          )}
        </div>
      )}

      {/* ── Filters ────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search..." className="pl-8" />
        </div>
        <select value={societyFilter} onChange={(e) => setSocietyFilter(e.target.value)} className="rounded-lg border bg-background px-3 py-2 text-sm">
          {SOCIETIES.map((s) => <option key={s} value={s}>{s === 'all' ? 'All Societies' : s}</option>)}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border bg-background px-3 py-2 text-sm">
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="deprecated">Obsolete</option>
        </select>
      </div>

      {/* ── Document Table ─────────────────────────────────────────── */}
      {loading ? (
        <p className="text-sm text-muted-foreground py-8 text-center">{t('common.loading')}</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">{t('common.noResults')}</p>
      ) : (
        <div className="rounded-lg border">
          <Table className="[&_td]:text-left [&_th]:text-left">
            <TableHeader>
              <TableRow>
                <TableHead><div className="inline-block resize-x overflow-auto min-w-[100px] cursor-pointer select-none" onClick={() => handleSort('source_filename')}>{t('admin.documents.table.filename')}{sortIcon('source_filename')}</div></TableHead>
                <TableHead><div className="inline-block resize-x overflow-auto min-w-[64px] cursor-pointer select-none" onClick={() => handleSort('classification_society')}>{t('admin.documents.table.society')}{sortIcon('classification_society')}</div></TableHead>
                <TableHead><div className="inline-block resize-x overflow-auto min-w-[64px]">{t('admin.documents.table.domain')}</div></TableHead>
                <TableHead><div className="inline-block resize-x overflow-auto min-w-[48px] cursor-pointer select-none" onClick={() => handleSort('chunks_count')}>{t('admin.documents.table.chunks')}{sortIcon('chunks_count')}</div></TableHead>
                <TableHead><div className="inline-block resize-x overflow-auto min-w-[64px] cursor-pointer select-none" onClick={() => handleSort('status')}>{t('admin.documents.table.status')}{sortIcon('status')}</div></TableHead>
                <TableHead><div className="inline-block resize-x overflow-auto min-w-[48px]">{t('admin.documents.table.actions')}</div></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((doc) => {
                // Try to parse filename for extra display fields
                const parsed = parseFilename(doc.source_filename);
                return (
                  <TableRow key={doc.doc_id}>
                    <TableCell className="font-medium text-sm max-w-[300px] truncate">{doc.source_filename}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="text-xs">{doc.classification_society || '—'}</Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {parsed.valid ? parsed.category : doc.domain}
                    </TableCell>
                    <TableCell className="text-xs font-mono text-muted-foreground">
                      {parsed.valid ? parsed.section : '—'}
                    </TableCell>
                    <TableCell className="text-xs text-left">{doc.domain}</TableCell>
                    <TableCell className="text-xs text-left">{doc.chunks_count}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="gap-1.5 text-xs">
                        <span className={`h-1.5 w-1.5 rounded-full ${STATUS_COLORS[doc.status] || 'bg-gray-400'}`} />
                        {doc.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="">
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setDeleteTarget(doc.doc_id)}>
                        <Trash2 className="h-4 w-4 text-muted-foreground" />
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Invalid filename dialog */}
      <Dialog open={invalidDialogOpen} onOpenChange={setInvalidDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invalid Filename Format</DialogTitle>
            <div className="text-sm text-muted-foreground space-y-2">
              <p>The following file{invalidFilenames.length > 1 ? 's do' : ' does'} not match the required format:</p>
              <div className="space-y-1">
                {invalidFilenames.map((name, i) => (
                  <div key={i} className="text-sm font-mono bg-muted px-2 py-1 rounded">{name}</div>
                ))}
              </div>
              <p className="font-medium text-foreground">Required format:</p>
              <div className="font-mono text-sm bg-muted px-2 py-1 rounded inline-block">
                [Society][Category][Section][Name][YYYYMM].ext
              </div>
              <p>Example: <code>[DNV][RU-SHIP][Pt.1-Ch.1][General regulations][202507].pdf</code></p>
            </div>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setInvalidDialogOpen(false)}>Understood</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Document</DialogTitle>
            <DialogDescription>Permanently delete this document and all its chunks? This action cannot be undone.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDelete}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
