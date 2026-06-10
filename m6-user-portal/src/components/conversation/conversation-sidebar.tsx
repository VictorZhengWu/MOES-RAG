/**
 * Full-featured conversation sidebar with login-state-aware rendering.
 *
 * Layout:
 * ┌──────────────────┐
 * │ [+ New Chat]     │
 * │ [🔍 Search chats]│
 * │ [🧠 Deep Research]│
 * ├──────────────────┤
 * │  Session history │ ← logged-in only; guest sees "Sign in"
 * │  (ScrollArea)    │
 * ├──────────────────┤
 * │ [⚙ Settings]    │
 * │ [❓ Help]        │
 * ├──────────────────┤
 * │ [👤 Name/Avatar] │ ← logged-in
 * │ [Log in]         │ ← guest
 * └──────────────────┘
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { useConversationStore } from '@/lib/stores/conversation-store';
import { useChatStore } from '@/lib/stores/chat-store';
import { ConversationItem } from './conversation-item';
import { ConversationSearch } from './conversation-search';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Plus,
  Brain,
  Settings,
  HelpCircle,
  LogIn,
  LogOut,
  Search,
} from 'lucide-react';

export function ConversationSidebar() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const { authStatus, user, logout } = useAuthStore();
  const {
    conversations,
    activeId,
    fetchConversations,
    setActiveId,
  } = useConversationStore();
  const clearMessages = useChatStore((s) => s.clearMessages);
  const isLoggedIn = authStatus === 'authenticated';

  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (isLoggedIn) fetchConversations(searchQuery);
  }, [isLoggedIn, fetchConversations, searchQuery]);

  const handleSearch = useCallback((q: string) => {
    setSearchQuery(q);
  }, []);

  const handleNewChat = () => {
    clearMessages();
    setActiveId(null);
    router.push(`/${locale}/chat`);
  };

  const handleSelect = (id: string) => {
    setActiveId(id);
    router.push(`/${locale}/chat/${id}`);
  };

  const handleDeepResearch = () => {
    router.push(`/${locale}/research`);
  };

  const userInitials = user?.username?.slice(0, 2).toUpperCase() || '??';

  return (
    <div className="flex h-full flex-col">
      {/* ── Top action buttons ── */}
      <div className="space-y-1 p-3">
        <Button
          variant="outline"
          className="w-full justify-start gap-2 h-9 text-sm"
          onClick={handleNewChat}
        >
          <Plus className="h-4 w-4" />
          {t('sidebar.newChat')}
        </Button>
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 h-9 text-sm text-muted-foreground"
        >
          <Search className="h-4 w-4" />
          {t('sidebar.searchChats')}
        </Button>
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 h-9 text-sm text-muted-foreground"
          disabled={!isLoggedIn}
          onClick={handleDeepResearch}
        >
          <Brain className="h-4 w-4" />
          {t('sidebar.deepResearch')}
        </Button>
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 h-9 text-sm text-muted-foreground"
          disabled={!isLoggedIn}
          onClick={() => router.push(`/${locale}/projects`)}
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
          </svg>
          {t('sidebar.projects')}
        </Button>
      </div>

      <Separator />

      {/* ── Conversation history ── */}
      {isLoggedIn ? (
        <>
          <div className="px-3 pt-2">
            <ConversationSearch onSearch={handleSearch} />
          </div>
          <ScrollArea className="flex-1">
            <div className="space-y-0.5 px-2">
              {conversations.length === 0 ? (
                <p className="px-3 py-8 text-center text-xs text-muted-foreground">
                  {t('conversation.empty')}
                </p>
              ) : (
                conversations.map((conv) => (
                  <ConversationItem
                    key={conv.conversation_id}
                    conversation={conv}
                    isActive={conv.conversation_id === activeId}
                    onSelect={() => handleSelect(conv.conversation_id)}
                  />
                ))
              )}
            </div>
          </ScrollArea>
        </>
      ) : (
        <div className="flex-1 flex items-center justify-center px-4">
          <p className="text-xs text-center text-muted-foreground">
            {t('conversation.guestEmpty')}
          </p>
        </div>
      )}

      <Separator />

      {/* ── Bottom: Settings, Help, Login/Avatar ── */}
      <div className="space-y-1 p-3">
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 h-9 text-sm text-muted-foreground"
          onClick={() => router.push(`/${locale}/settings`)}
        >
          <Settings className="h-4 w-4" />
          {t('sidebar.settings')}
        </Button>
        <Button
          variant="ghost"
          className="w-full justify-start gap-2 h-9 text-sm text-muted-foreground"
          onClick={() => router.push(`/${locale}/help`)}
        >
          <HelpCircle className="h-4 w-4" />
          {t('sidebar.help')}
        </Button>

        <Separator className="my-2" />

        {isLoggedIn ? (
          <div className="flex items-center gap-2 px-1 py-1">
            <Avatar className="h-7 w-7">
              <AvatarFallback className="text-xs">
                {userInitials}
              </AvatarFallback>
            </Avatar>
            <span className="flex-1 truncate text-sm">
              {user?.username}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={logout}
              title={t('sidebar.logOut')}
            >
              <LogOut className="h-3 w-3" />
            </Button>
          </div>
        ) : (
          <Button
            variant="outline"
            className="w-full justify-start gap-2 h-9 text-sm"
            onClick={() => router.push(`/${locale}/login?redirect=${encodeURIComponent(pathname)}`)}
          >
            <LogIn className="h-4 w-4" />
            {t('sidebar.logIn')}
          </Button>
        )}
      </div>
    </div>
  );
}
