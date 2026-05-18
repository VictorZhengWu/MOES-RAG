/**
 * User Management — list, create, edit, suspend/reactivate.
 * Social account badges show linked providers.
 * Roles from shared USER_ROLES config — same as LLM Config page.
 */

'use client';

import React, { useEffect, useState, useCallback } from 'react';
import type { AdminUser } from '@/types';
import { useTranslations } from 'next-intl';
import { listUsers, createUser, deleteUser } from '@/lib/api/users';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog';
import {
  Plus, Search, Pencil, Trash2, Loader2, UserPlus, ShieldBan, ShieldCheck,
} from 'lucide-react';

// ── Role config — same as LLM Config page (single source of truth) ─
const USER_ROLES = [
  { value: 'free', label: 'Free', level: 1 },
  { value: 'basic', label: 'Basic', level: 2 },
  { value: 'pro', label: 'Pro', level: 3 },
  { value: 'enterprise', label: 'Enterprise', level: 4 },
  { value: 'editor', label: 'Editor', level: 4 },
  { value: 'admin', label: 'Admin', level: 5 },
];

const SOCIAL_PROVIDERS = ['google', 'microsoft', 'apple', 'facebook', 'x', 'wechat'] as const;

const STATUS_COLORS: Record<string, string> = { active: 'bg-green-500', suspended: 'bg-yellow-500' };

interface MockUser extends AdminUser {
  social_accounts: string[];
  quota_limit: number;
}

const emptyForm = (): Partial<MockUser> => ({
  username: '', email: '', role: 'free',
  is_active: true, social_accounts: [],
  quota_limit: 1000, total_queries: 0,
});

export default function UsersPage() {
  const t = useTranslations();
  const [users, setUsers] = useState<MockUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentUser, setCurrentUser] = useState('');

  useEffect(() => { setCurrentUser(sessionStorage.getItem('m7-admin-user') || ''); }, []);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [sortField, setSortField] = useState('username');
  const [sortAsc, setSortAsc] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<MockUser | null>(null);
  const [form, setForm] = useState<Partial<MockUser>>(emptyForm());
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [suspendTarget, setSuspendTarget] = useState<MockUser | null>(null);

  const fetchUsers = useCallback(async () => {
    setLoading(true);
    try {
      const res = await listUsers();
      // Enrich with mock social data for Phase 1
      const enriched: MockUser[] = (res.users || []).map((u: AdminUser, i: number) => ({
        ...u,
        social_accounts: i === 0 ? ['google', 'microsoft'] : i === 1 ? ['wechat'] : [],
        quota_limit: 1000,
      }));
      setUsers(enriched);
    } catch { setUsers([]); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  // Sort: admin/editor first, then by role level descending
  const ADMIN_ROLES = ['admin', 'editor'];
  const filtered = [...users]
    .filter((u) => {
      const ms = !search || u.username.toLowerCase().includes(search.toLowerCase()) ||
        u.email.toLowerCase().includes(search.toLowerCase());
      const mr = roleFilter === 'all' || u.role === roleFilter;
      const mst = statusFilter === 'all' || (u.is_active ? 'active' : 'suspended') === statusFilter;
      return ms && mr && mst;
    })
    .sort((a, b) => {
      const aAdmin = ADMIN_ROLES.includes(a.role) ? 0 : 1;
      const bAdmin = ADMIN_ROLES.includes(b.role) ? 0 : 1;
      if (aAdmin !== bAdmin) return aAdmin - bAdmin;
      return a.username.localeCompare(b.username);
    });

  // Find the split point between admin/editor and regular users
  let showDivider = false;
  let splitIndex = filtered.findIndex((u) => !ADMIN_ROLES.includes(u.role));
  if (splitIndex > 0 && splitIndex < filtered.length) showDivider = true;
  if (splitIndex === -1) splitIndex = filtered.length;

  // Apply sort
  const sorted = [...filtered].sort((a, b) => {
    const va = (a as any)[sortField] ?? '';
    const vb = (b as any)[sortField] ?? '';
    const cmp = String(va).localeCompare(String(vb), undefined, { numeric: true });
    return sortAsc ? cmp : -cmp;
  });

  const handleUserSort = (field: string) => {
    if (sortField === field) setSortAsc(!sortAsc);
    else { setSortField(field); setSortAsc(true); }
  };
  const userSortIcon = (field: string) =>
    sortField === field ? (sortAsc ? ' ▲' : ' ▼') : '';

  const openCreate = () => { setEditingUser(null); setForm(emptyForm()); setDialogOpen(true); };
  const openEdit = (u: MockUser) => { setEditingUser(u); setForm({ ...u }); setDialogOpen(true); };

  const handleSave = async () => {
    if (!form.username?.trim() || !form.email?.trim()) return;
    setSaving(true);
    try {
      if (editingUser) {
        // Phase 2: PUT /api/v1/admin/users/{id}
      } else {
        await createUser({ username: form.username, email: form.email, role: form.role });
      }
      setDialogOpen(false);
      fetchUsers();
    } catch { /* mock */ }
    finally { setSaving(false); }
  };

  const handleSuspend = async (u: MockUser) => {
    if (u.username === currentUser) return; // prevent self-disable
    setUsers((prev) =>
      prev.map((user) =>
        user.user_id === u.user_id ? { ...user, is_active: !user.is_active } : user,
      ),
    );
    setSuspendTarget(null);
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    await deleteUser(deleteTarget);
    setUsers((prev) => prev.filter((u) => u.user_id !== deleteTarget));
    setDeleteTarget(null);
  };

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">{t('admin.users.title')}</h1>
          <p className="text-sm text-muted-foreground mt-1">{t('admin.users.subtitle')}</p>
        </div>
        <Button onClick={openCreate} size="sm" className="gap-1.5">
          <UserPlus className="h-4 w-4" /> Add User
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-4">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search users..." className="pl-8" />
        </div>
        <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} className="rounded-lg border bg-background px-3 py-2 text-sm">
          <option value="all">All Roles</option>
          {USER_ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-lg border bg-background px-3 py-2 text-sm">
          <option value="all">All Status</option>
          <option value="active">Active</option>
          <option value="suspended">Suspended</option>
        </select>
      </div>

      {/* User table */}
      {loading ? (
        <p className="text-sm text-muted-foreground py-8 text-center">Loading...</p>
      ) : sorted.length === 0 ? (
        <p className="text-sm text-muted-foreground py-8 text-center">No users found.</p>
      ) : (
        <div className="rounded-lg border">
          <Table className="[&_td]:text-left [&_th]:text-left">
            <TableHeader>
              <TableRow>
                <TableHead className="cursor-pointer select-none resize-x overflow-auto" onClick={() => handleUserSort('username')}>Username{userSortIcon('username')}</TableHead>
                <TableHead className="cursor-pointer select-none resize-x overflow-auto" onClick={() => handleUserSort('email')}>Email{userSortIcon('email')}</TableHead>
                <TableHead className="cursor-pointer select-none resize-x overflow-auto" onClick={() => handleUserSort('role')}>Role{userSortIcon('role')}</TableHead>
                <TableHead className="resize-x overflow-auto">Social</TableHead>
                <TableHead className="resize-x overflow-auto">Status</TableHead>
                <TableHead className="cursor-pointer select-none resize-x overflow-auto" onClick={() => handleUserSort('total_queries')}>Queries{userSortIcon('total_queries')}</TableHead>
                <TableHead className="resize-x overflow-auto">API Keys</TableHead>
                <TableHead className="resize-x overflow-auto">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map((u, i) => (
                <React.Fragment key={u.user_id}>
                  {/* Divider between admin/editor and regular users */}
                  {showDivider && i === splitIndex && (
                    <TableRow className="border-t-2 border-border">
                      <TableCell colSpan={8} className="py-2 text-xs text-muted-foreground font-medium">
                        ── Regular Users ──
                      </TableCell>
                    </TableRow>
                  )}
                <TableRow className={!u.is_active ? 'opacity-60' : ''}>
                  <TableCell className="font-medium text-sm">{u.username}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{u.email}</TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="text-[11px]">{u.role}</Badge>
                  </TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      {u.social_accounts.length === 0 ? (
                        <span className="text-xs text-muted-foreground">Email only</span>
                      ) : (
                        u.social_accounts.map((s) => (
                          <Badge key={s} variant="outline" className="text-[10px]">{s}</Badge>
                        ))
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="gap-1.5 text-[11px]">
                      <span className={`h-1.5 w-1.5 rounded-full ${STATUS_COLORS[u.is_active ? 'active' : 'suspended']}`} />
                      {u.is_active ? 'Active' : 'Suspended'}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm">{u.total_queries.toLocaleString()}</TableCell>
                  <TableCell className="text-sm">{u.api_key_count}</TableCell>
                  <TableCell>
                    <div className="flex justify-end gap-1">
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => openEdit(u)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8"
                        onClick={() => setSuspendTarget(u)}
                        disabled={u.username === currentUser}
                        title={u.username === currentUser ? 'Cannot suspend yourself' : u.is_active ? 'Suspend' : 'Reactivate'}>
                        {u.is_active ? <ShieldBan className="h-4 w-4 text-muted-foreground" /> : <ShieldCheck className="h-4 w-4 text-green-500" />}
                      </Button>
                      <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setDeleteTarget(u.user_id)}>
                        <Trash2 className="h-4 w-4 text-muted-foreground" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
                </React.Fragment>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editingUser ? 'Edit User' : 'Create User'}</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div>
              <label className="text-xs font-medium text-muted-foreground">Username</label>
              <Input value={form.username || ''} onChange={(e) => setForm({ ...form, username: e.target.value })}
                placeholder="Username" className="mt-1" />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground">Email</label>
              <Input type="email" value={form.email || ''} onChange={(e) => setForm({ ...form, email: e.target.value })}
                placeholder="Email" className="mt-1" />
            </div>
            {!editingUser && (
              <div>
                <label className="text-xs font-medium text-muted-foreground">Password</label>
                <Input type="password" value={(form as Record<string, string>).password || ''}
                  onChange={(e) => setForm({ ...form, password: e.target.value } as Partial<MockUser>)}
                  placeholder="Min 8 characters" className="mt-1" />
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs font-medium text-muted-foreground">Role</label>
                <select value={form.role || 'free'} onChange={(e) => setForm({ ...form, role: e.target.value })}
                  className="mt-1 w-full rounded-lg border bg-background px-3 py-2 text-sm">
                  {USER_ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-medium text-muted-foreground">Monthly Quota</label>
                <Input type="number" value={form.quota_limit || 1000}
                  onChange={(e) => setForm({ ...form, quota_limit: parseInt(e.target.value) || 1000 })}
                  className="mt-1" />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving || !form.username?.trim() || !form.email?.trim()}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              {editingUser ? 'Save' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Suspend/Reactivate confirmation */}
      <Dialog open={!!suspendTarget} onOpenChange={(o) => !o && setSuspendTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{suspendTarget?.is_active ? 'Suspend User' : 'Reactivate User'}</DialogTitle>
            <div className="text-sm text-muted-foreground">
              {suspendTarget?.is_active
                ? `Suspend "${suspendTarget?.username}"? They will not be able to access the system until reactivated.`
                : `Reactivate "${suspendTarget?.username}"? They will regain full access to the system.`
              }
            </div>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSuspendTarget(null)}>Cancel</Button>
            <Button variant={suspendTarget?.is_active ? 'destructive' : 'default'} onClick={() => suspendTarget && handleSuspend(suspendTarget)}>
              {suspendTarget?.is_active ? 'Suspend' : 'Reactivate'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete User</DialogTitle>
            <div className="text-sm text-muted-foreground">Permanently delete this user? All associated data will be removed. This cannot be undone.</div>
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
