/**
 * Profile settings tab: displays and (in future) edits user information.
 *
 * WHY: Users need to view and manage their account details. Phase 1
 * shows mock profile data. Phase 2 will connect to real auth/user
 * database. The "Delete Account" button includes a confirmation
 * step to prevent accidental deletion.
 */

'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Loader2 } from 'lucide-react';
import { deleteAccount } from '@/lib/api/conversations';
import { useRouter } from 'next/navigation';
import { useLocale } from 'next-intl';

function DeleteAccountButton() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const { user, token, logout } = useAuthStore();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState('');

  if (!user) return null;

  const handleDelete = async () => {
    setDeleting(true);
    setError('');
    try {
      await deleteAccount(token ?? undefined);
      logout();
      router.push(`/${locale}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete account');
      setDeleting(false);
      setConfirming(false);
    }
  };

  if (!confirming) {
    return (
      <div className="mt-3 space-y-2">
        <Button variant="destructive" size="sm" onClick={() => setConfirming(true)}>
          Delete Account
        </Button>
      </div>
    );
  }

  return (
    <div className="mt-3 space-y-3 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
      <p className="text-sm font-medium text-destructive">Are you absolutely sure?</p>
      <p className="text-xs text-muted-foreground">
        This will permanently delete your account, all conversations, and API keys. This action cannot be undone.
      </p>
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex gap-2">
        <Button variant="destructive" size="sm" onClick={handleDelete} disabled={deleting}>
          {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" /> : null}
          Yes, delete my account
        </Button>
        <Button variant="outline" size="sm" onClick={() => { setConfirming(false); setError(''); }} disabled={deleting}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

export function ProfileTab() {
  const t = useTranslations();
  const { user } = useAuthStore();
  const isLoggedIn = !!user;

  const initials = user?.username?.slice(0, 2).toUpperCase() || '??';

  if (!isLoggedIn) {
    return (
      <div className="py-12 text-center">
        <p className="text-sm text-muted-foreground">
          {t('conversation.guestEmpty')}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Avatar + name header — click avatar to change */}
      <div className="flex items-center gap-3">
        <label className="relative cursor-pointer group">
          <Avatar className="h-16 w-16">
            {user?.avatar_url ? (
              <img src={user.avatar_url} alt={user.username} className="h-full w-full object-cover" />
            ) : (
              <AvatarFallback className="text-lg">{initials}</AvatarFallback>
            )}
          </Avatar>
          <div className="absolute inset-0 flex items-center justify-center rounded-full bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity">
            <span className="text-white text-[10px] font-medium">Edit</span>
          </div>
          <input
            type="file"
            accept="image/*"
            className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              // Validate file type
              const allowed = ['.png', '.jpg', '.jpeg', '.gif', '.webp'];
              const ext = file.name.toLowerCase().substring(file.name.lastIndexOf('.'));
              if (!allowed.includes(ext)) { alert('Only PNG, JPG, GIF, WebP images are allowed.'); return; }
              // Validate file size (5MB max)
              if (file.size > 5 * 1024 * 1024) { alert('Avatar too large. Maximum: 5MB.'); return; }
              const token = useAuthStore.getState().token;
              const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
              const form = new FormData();
              form.append('file', file);
              try {
                const res = await fetch(`${baseUrl}/api/v1/user/avatar`, {
                  method: 'POST', headers: token ? { Authorization: `Bearer ${token}` } : {}, body: form,
                });
                if (res.ok) {
                  const data = await res.json();
                  useAuthStore.getState().login(
                    { ...useAuthStore.getState().user!, avatar_url: data.avatar_url },
                    token || '',
                  );
                }
              } catch { /* M8 not running */ }
            }}
          />
        </label>
        <div>
          <p className="font-medium">{user?.username}</p>
          <p className="text-xs text-muted-foreground">{user?.email}</p>
        </div>
      </div>

      <Separator />

      {/* User info fields (read-only for Phase 1) */}
      <div className="space-y-3">
        <div>
          <label className="text-xs font-medium text-muted-foreground">Username</label>
          <Input value={user?.username || ''} disabled className="mt-1" />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Email</label>
          <Input value={user?.email || ''} disabled className="mt-1" />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground">Phone</label>
          <Input value="+47 123 45 678" disabled className="mt-1" />
        </div>
      </div>

      <Separator />

      {/* Danger zone */}
      <div>
        <h4 className="text-sm font-medium text-destructive">Danger Zone</h4>
        <p className="mt-1 text-xs text-muted-foreground">
          Once you delete your account, there is no going back. Please be certain.
        </p>
        <DeleteAccountButton />
      </div>
    </div>
  );
}
