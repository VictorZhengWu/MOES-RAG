/**
 * Collapsed sidebar: narrow icon strip (56px) shown when sidebar is
 * toggled closed or viewport is narrow. Icons with tooltip labels.
 *
 * NOTE: TooltipTrigger already renders a <button> (Base UI).
 * Do NOT nest another <button> inside — use className/onClick directly.
 */

'use client';

import { useRouter, usePathname } from 'next/navigation';
import { useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { useChatStore } from '@/lib/stores/chat-store';
import { useConversationStore } from '@/lib/stores/conversation-store';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Separator } from '@/components/ui/separator';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import {
  Plus, Search, Brain, Settings, HelpCircle, LogIn, PanelLeft,
} from 'lucide-react';

interface Props { onExpand: () => void; }

export function CollapsedSidebar({ onExpand }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();
  const { authStatus, user } = useAuthStore();
  const clearMessages = useChatStore((s) => s.clearMessages);
  const setActiveId = useConversationStore((s) => s.setActiveId);
  const isLoggedIn = authStatus === 'authenticated';
  const initials = user?.username?.slice(0, 2).toUpperCase() || '??';

  const newChat = () => {
    clearMessages(); setActiveId(null); router.push(`/${locale}/chat`);
  };

  const iconBtn = 'flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors text-muted-foreground';

  return (
    <div className="w-[56px] shrink-0 border-r bg-muted/30 flex flex-col items-center py-3 gap-2">
      <Tooltip>
        <TooltipTrigger className={iconBtn} onClick={onExpand}>
          <PanelLeft className="h-4 w-4" />
        </TooltipTrigger>
        <TooltipContent side="right">Expand sidebar</TooltipContent>
      </Tooltip>
      <Separator className="w-8" />
      <Tooltip>
        <TooltipTrigger className={iconBtn} onClick={newChat}>
          <Plus className="h-4 w-4" />
        </TooltipTrigger>
        <TooltipContent side="right">New Chat</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger className={iconBtn}>
          <Search className="h-4 w-4" />
        </TooltipTrigger>
        <TooltipContent side="right">Search chats</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger className={iconBtn + ' disabled:opacity-30'} disabled={!isLoggedIn}>
          <Brain className="h-4 w-4" />
        </TooltipTrigger>
        <TooltipContent side="right">Deep Research</TooltipContent>
      </Tooltip>
      <div className="flex-1" />
      <Tooltip>
        <TooltipTrigger className={iconBtn} onClick={() => router.push(`/${locale}/settings`)}>
          <Settings className="h-4 w-4" />
        </TooltipTrigger>
        <TooltipContent side="right">Settings</TooltipContent>
      </Tooltip>
      <Tooltip>
        <TooltipTrigger className={iconBtn}>
          <HelpCircle className="h-4 w-4" />
        </TooltipTrigger>
        <TooltipContent side="right">Help</TooltipContent>
      </Tooltip>
      <Separator className="w-8" />
      {isLoggedIn ? (
        <Tooltip>
          <TooltipTrigger className="flex h-9 w-9 items-center justify-center">
            <Avatar className="h-7 w-7"><AvatarFallback className="text-[10px]">{initials}</AvatarFallback></Avatar>
          </TooltipTrigger>
          <TooltipContent side="right">{user?.username}</TooltipContent>
        </Tooltip>
      ) : (
        <Tooltip>
          <TooltipTrigger className={iconBtn} onClick={() => router.push(`/${locale}/login?redirect=${encodeURIComponent(pathname)}`)}>
            <LogIn className="h-4 w-4" />
          </TooltipTrigger>
          <TooltipContent side="right">Log in</TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}
