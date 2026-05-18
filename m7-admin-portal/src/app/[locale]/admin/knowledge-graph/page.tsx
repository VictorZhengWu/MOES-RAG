/**
 * Knowledge Graph Browser — entities, relations, cross-society mapping.
 * Data from Mock Server (Phase 1) or real KG database (Phase 2).
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import type { KGEntity, KGRelation } from '@/types';
import { listEntities, listRelations } from '@/lib/api/knowledge-graph';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Search, GitBranch, ArrowRightLeft, Link2, FileText, Tag, Pencil, Trash2, X, Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';

const ENTITY_TYPES: Record<string, string> = {
  regulation_clause: 'Regulation Clause',
  vessel_type: 'Vessel Type',
  system: 'System',
  equipment: 'Equipment',
  manufacturer: 'Manufacturer',
};

const RELATION_TYPES: Record<string, string> = {
  regulates: 'Regulates',
  references: 'References',
  applies_to: 'Applies To',
  equivalent_to: 'Equivalent To',
  replaces: 'Replaces',
  requires: 'Requires',
  prohibits: 'Prohibits',
};

// Mock cross-society mappings for Phase 1
const MOCK_CROSS_REFS = [
  {
    source: 'DNV Pt.4 Ch.3 Sec.5',
    target: 'ABS Pt.5B Sec.3-2',
    topic: 'LNG Cargo Tank Boundaries',
    confidence: 0.95,
  },
  {
    source: 'DNV Pt.3 Ch.3 Sec.2',
    target: 'CCS Pt.3 Ch.2 Sec.1',
    topic: 'Structural Design Principles',
    confidence: 0.88,
  },
  {
    source: 'ABS Pt.4 Ch.2 Sec.1',
    target: 'LR Pt.4 Ch.2 Sec.1',
    topic: 'Welding Requirements',
    confidence: 0.92,
  },
];

export default function KnowledgeGraphPage() {
  const [entities, setEntities] = useState<KGEntity[]>([]);
  const [relations, setRelations] = useState<KGRelation[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedEntity, setSelectedEntity] = useState<KGEntity | null>(null);
  const [entityTypeFilter, setEntityTypeFilter] = useState('all');
  const [relationTypeFilter, setRelationTypeFilter] = useState('all');
  const [editingEntity, setEditingEntity] = useState<KGEntity | null>(null);
  const [editName, setEditName] = useState('');
  const [deleteEntityTarget, setDeleteEntityTarget] = useState<KGEntity | null>(null);
  const [deleteRelationTarget, setDeleteRelationTarget] = useState<KGRelation | null>(null);
  const t = useTranslations();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [eRes, rRes] = await Promise.all([listEntities(), listRelations()]);
      setEntities(eRes.entities || []);
      setRelations(rRes.relations || []);
    } catch { setEntities([]); setRelations([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const filteredEntities = entities.filter((e) => {
    const ms = !search || e.name.toLowerCase().includes(search.toLowerCase());
    const mt = entityTypeFilter === 'all' || e.entity_type === entityTypeFilter;
    return ms && mt;
  });

  const filteredRelations = relations.filter((r) => {
    const ms = !search || r.source_entity_name.toLowerCase().includes(search.toLowerCase()) ||
      r.target_entity_name.toLowerCase().includes(search.toLowerCase());
    const mt = relationTypeFilter === 'all' || r.relation_type === relationTypeFilter;
    return ms && mt;
  });

  // ── Edit / Delete actions (Phase 1: local state) ─────────────
  const handleSaveEntity = () => {
    if (!editingEntity || !editName.trim()) return;
    setEntities((prev) => prev.map((e) => e.entity_id === editingEntity.entity_id ? { ...e, name: editName } : e));
    if (selectedEntity?.entity_id === editingEntity.entity_id) {
      setSelectedEntity({ ...selectedEntity, name: editName });
    }
    setEditingEntity(null);
  };

  const handleDeleteEntity = () => {
    if (!deleteEntityTarget) return;
    setEntities((prev) => prev.filter((e) => e.entity_id !== deleteEntityTarget.entity_id));
    setRelations((prev) => prev.filter((r) => r.source_entity_id !== deleteEntityTarget.entity_id && r.target_entity_id !== deleteEntityTarget.entity_id));
    setSelectedEntity(null);
    setDeleteEntityTarget(null);
  };

  const handleDeleteRelation = () => {
    if (!deleteRelationTarget) return;
    setRelations((prev) => prev.filter((r) => r.relation_id !== deleteRelationTarget.relation_id));
    setDeleteRelationTarget(null);
  };

  // Relations for selected entity
  const entityRelations = selectedEntity
    ? relations.filter((r) => r.source_entity_id === selectedEntity.entity_id || r.target_entity_id === selectedEntity.entity_id)
    : [];

  if (loading) return <div className="p-8 text-sm text-muted-foreground">Loading...</div>;

  return (
    <div className="p-8">
      <h1 className="text-xl font-bold mb-1">Knowledge Graph</h1>
      <p className="text-sm text-muted-foreground mb-6">{t('admin.knowledgeGraph.subtitle')}</p>

      <Tabs defaultValue="entities" className="w-full">
        <TabsList className="mb-4">
          <TabsTrigger value="entities" className="gap-1.5">
            <Tag className="h-3.5 w-3.5" /> Entities
          </TabsTrigger>
          <TabsTrigger value="relations" className="gap-1.5">
            <Link2 className="h-3.5 w-3.5" /> Relations
          </TabsTrigger>
          <TabsTrigger value="crossref" className="gap-1.5">
            <ArrowRightLeft className="h-3.5 w-3.5" /> Cross-Reference
          </TabsTrigger>
        </TabsList>

        {/* ── Entities Tab ──────────────────────────────────────── */}
        <TabsContent value="entities">
          <div className="flex gap-6">
            {/* Left: entity list */}
            <div className="w-80 shrink-0 space-y-3">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search entities..." className="pl-8" />
              </div>
              <select value={entityTypeFilter} onChange={(e) => setEntityTypeFilter(e.target.value)}
                className="w-full rounded-lg border bg-background px-3 py-2 text-sm">
                <option value="all">All</option>
                {Object.entries(ENTITY_TYPES).map(([k, v]) => <option key={k} value={k}>{t(`admin.knowledgeGraph.entityTypes.${k}` as any) || v}</option>)}
              </select>
              <ScrollArea className="h-[500px]">
                <div className="space-y-1">
                  {filteredEntities.map((e) => (
                    <button
                      key={e.entity_id}
                      onClick={() => setSelectedEntity(e)}
                      className={`w-full text-left rounded-lg px-3 py-2 text-sm transition-colors ${
                        selectedEntity?.entity_id === e.entity_id ? 'bg-accent' : 'hover:bg-muted'
                      }`}
                    >
                      <p className="font-medium truncate">{e.name}</p>
                      <Badge variant="outline" className="text-[10px] mt-0.5">
                        {ENTITY_TYPES[e.entity_type] || e.entity_type}
                      </Badge>
                    </button>
                  ))}
                </div>
              </ScrollArea>
            </div>

            {/* Right: entity detail */}
            <div className="flex-1">
              {selectedEntity ? (
                <div className="space-y-4">
                  <Card>
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-base">{selectedEntity.name}</CardTitle>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="icon" className="h-7 w-7"
                            onClick={() => { setEditingEntity(selectedEntity); setEditName(selectedEntity.name); }}>
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7"
                            onClick={() => setDeleteEntityTarget(selectedEntity)}>
                            <Trash2 className="h-3.5 w-3.5 text-destructive" />
                          </Button>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="flex gap-2 mb-3">
                        <Badge>{ENTITY_TYPES[selectedEntity.entity_type] || selectedEntity.entity_type}</Badge>
                        {selectedEntity.source_doc_id && (
                          <Badge variant="outline" className="gap-1">
                            <FileText className="h-3 w-3" />
                            {selectedEntity.source_doc_id}
                          </Badge>
                        )}
                      </div>
                      {selectedEntity.properties && Object.keys(selectedEntity.properties).length > 0 && (
                        <div className="space-y-1">
                          <p className="text-xs font-medium text-muted-foreground">{t('knowledge.table.status')}</p>
                          {Object.entries(selectedEntity.properties).map(([k, v]) => (
                            <div key={k} className="flex gap-2 text-sm">
                              <span className="text-muted-foreground">{k}:</span>
                              <span>{String(v)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  {/* Related relations */}
                  {entityRelations.length > 0 && (
                    <div>
                      <h3 className="text-sm font-medium mb-2">Related Relations ({entityRelations.length})</h3>
                      <div className="space-y-2">
                        {entityRelations.map((r) => (
                          <Card key={r.relation_id}>
                            <CardContent className="p-3 text-sm">
                              <div className="flex items-center gap-2">
                                <span className="font-medium">{r.source_entity_name}</span>
                                <Badge variant="secondary" className="text-[10px]">
                                  {RELATION_TYPES[r.relation_type] || r.relation_type}
                                </Badge>
                                <span className="font-medium">{r.target_entity_name}</span>
                              </div>
                              <p className="text-xs text-muted-foreground mt-1">
                                Confidence: {(r.confidence * 100).toFixed(0)}%
                              </p>
                            </CardContent>
                          </Card>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex items-center justify-center h-[500px] text-sm text-muted-foreground">
                  Select an entity to view details
                </div>
              )}
            </div>
          </div>
        </TabsContent>

        {/* ── Relations Tab ──────────────────────────────────────── */}
        <TabsContent value="relations">
          <div className="flex gap-3 mb-4">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search relations..." className="pl-8" />
            </div>
            <select value={relationTypeFilter} onChange={(e) => setRelationTypeFilter(e.target.value)}
              className="rounded-lg border bg-background px-3 py-2 text-sm">
              <option value="all">All Types</option>
              {Object.entries(RELATION_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="space-y-2">
            {filteredRelations.map((r) => (
              <Card key={r.relation_id}>
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <span className="text-sm font-medium truncate max-w-[240px]">{r.source_entity_name}</span>
                    <Badge variant="secondary" className="text-[10px] shrink-0">
                      {RELATION_TYPES[r.relation_type] || r.relation_type}
                    </Badge>
                    <span className="text-sm font-medium truncate max-w-[240px]">{r.target_entity_name}</span>
                  </div>
                  <Badge variant="outline" className="text-[10px] shrink-0 ml-3">
                    {(r.confidence * 100).toFixed(0)}% confident
                  </Badge>
                  <Button variant="ghost" size="icon" className="h-7 w-7 ml-1"
                    onClick={() => setDeleteRelationTarget(r)}>
                    <Trash2 className="h-3.5 w-3.5 text-destructive" />
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        {/* ── Cross-Reference Tab ────────────────────────────────── */}
        <TabsContent value="crossref">
          <div className="space-y-2">
            <p className="text-sm text-muted-foreground mb-4">
              Cross-society regulation mappings — equivalent clauses across different classification societies.
            </p>
            {MOCK_CROSS_REFS.map((cr, i) => (
              <Card key={i}>
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-3 min-w-0">
                    <Badge variant="secondary" className="shrink-0">{cr.source}</Badge>
                    <ArrowRightLeft className="h-4 w-4 text-muted-foreground shrink-0" />
                    <Badge variant="secondary" className="shrink-0">{cr.target}</Badge>
                    <span className="text-sm text-muted-foreground truncate">— {cr.topic}</span>
                  </div>
                  <Badge variant="outline" className="text-[10px] shrink-0 ml-3">
                    {(cr.confidence * 100).toFixed(0)}% match
                  </Badge>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>
      </Tabs>

      {/* Edit Entity Dialog */}
      <Dialog open={!!editingEntity} onOpenChange={(o) => !o && setEditingEntity(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Edit Entity</DialogTitle></DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Name</label>
              <Input value={editName} onChange={(e) => setEditName(e.target.value)} className="mt-1" />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingEntity(null)}>Cancel</Button>
            <Button onClick={handleSaveEntity}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Entity Dialog */}
      <Dialog open={!!deleteEntityTarget} onOpenChange={(o) => !o && setDeleteEntityTarget(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Delete Entity</DialogTitle></DialogHeader>
          <div className="text-sm text-muted-foreground">
            Delete "{deleteEntityTarget?.name}"? This will also remove all its relations.
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteEntityTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDeleteEntity}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Relation Dialog */}
      <Dialog open={!!deleteRelationTarget} onOpenChange={(o) => !o && setDeleteRelationTarget(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Delete Relation</DialogTitle></DialogHeader>
          <div className="text-sm text-muted-foreground">
            Delete this relation? This cannot be undone.
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteRelationTarget(null)}>Cancel</Button>
            <Button variant="destructive" onClick={handleDeleteRelation}>Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
