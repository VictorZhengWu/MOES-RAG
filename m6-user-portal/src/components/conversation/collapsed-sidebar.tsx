/**
 * Collapsed sidebar: narrow icon strip (56px) shown when sidebar is
 * toggled closed or viewport is narrow. Each icon represents a
 * sidebar function — clicking either navigates or expands the sidebar.
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
  Plus,
  Search,
  Brain,
  Settings,
  HelpCircle,
  LogIn,
  PanelLeft,
} from 'lucide-react';

interface Props {
  onExpand: () => void;
}

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
    clearMessages();
    setActiveId(null);
    router.push(`/${locale}/chat`);
  };

  return (
    <div className="w-[56px] shrink-0 border-r bg-muted/30 flex flex-col items-center py-3 gap-2 transition-all duration-200">
      {/* Expand button */}
      <Tooltip>
        <TooltipTrigger>
          <button onClick={onExpand} className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors">
            <PanelLeft className="h-4 w-4 text-muted-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right">Expand sidebar</TooltipContent>
      </Tooltip>

      <Separator className="w-8" />

      {/* New Chat */}
      <Tooltip>
        <TooltipTrigger>
          <button onClick={newChat} className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors">
            <Plus className="h-4 w-4 text-muted-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right">New Chat</TooltipContent>
      </Tooltip>

      {/* Search */}
      <Tooltip>
        <TooltipTrigger>
          <button className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors">
            <Search className="h-4 w-4 text-muted-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right">Search chats</TooltipContent>
      </Tooltip>

      {/* Deep Research */}
      <Tooltip>
        <TooltipTrigger>
          <button disabled={!isLoggedIn} className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors disabled:opacity-30">
            <Brain className="h-4 w-4 text-muted-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right">Deep Research</TooltipContent>
      </Tooltip>

      <div className="flex-1" />

      {/* Settings */}
      <Tooltip>
        <TooltipTrigger>
          <button onClick={() => router.push(`/${locale}/settings`)} className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors">
            <Settings className="h-4 w-4 text-muted-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right">Settings</TooltipContent>
      </Tooltip>

      {/* Help */}
      <Tooltip>
        <TooltipTrigger>
          <button className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors">
            <HelpCircle className="h-4 w-4 text-muted-foreground" />
          </button>
        </TooltipTrigger>
        <TooltipContent side="right">Help</TooltipContent>
      </Tooltip>

      <Separator className="w-8" />

      {/* Login / Avatar */}
      {isLoggedIn ? (
        <Tooltip>
          <TooltipTrigger>
            <button className="flex h-9 w-9 items-center justify-center">
              <Avatar className="h-7 w-7">
                <AvatarFallback className="text-[10px]">{initials}</AvatarFallback>
              </Avatar>
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">{user?.username}</TooltipContent>
        </Tooltip>
      ) : (
        <Tooltip>
          <TooltipTrigger>
            <button onClick={() => router.push(`/${locale}/login?redirect=${encodeURIComponent(pathname)}`)} className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted transition-colors">
              <LogIn className="h-4 w-4 text-muted-foreground" />
            </button>
          </TooltipTrigger>
          <TooltipContent side="right">Log in</TooltipContent>
        </Tooltip>
      )}
    </div>
  );
}
