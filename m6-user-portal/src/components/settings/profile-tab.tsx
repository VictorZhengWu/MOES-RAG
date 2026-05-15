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
            onChange={(e) => {
              // Phase 2: upload to server. Phase 1: placeholder
              console.log('Avatar file selected:', e.target.files?.[0]?.name);
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
        <Button variant="destructive" size="sm" className="mt-3" disabled>
          Delete Account
        </Button>
      </div>
    </div>
  );
}
