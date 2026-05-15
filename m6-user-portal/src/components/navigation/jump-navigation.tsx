/**
 * Right-side narrow strip showing all user questions in the current chat.
 *
 * Hover over a question icon to see a preview; click to scroll to that
 * message in the chat area. Only appears when there are >= 2 user messages.
 *
 * WHY: In long conversations with dozens of exchanges, users need a
 * quick way to jump to earlier questions. DeepSeek and ChatGPT both
 * have this feature. The strip is 48px wide and non-intrusive.
 */

'use client';

import { useChatStore } from '@/lib/stores/chat-store';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip';
import { MessageSquare } from 'lucide-react';

export function JumpNavigation() {
  const messages = useChatStore((s) => s.messages);

  // Extract user messages with their indices
  const userMessages = messages
    .map((msg, i) => ({ ...msg, index: i }))
    .filter((msg) => msg.role === 'user');

  // Don't show for single-question chats
  if (userMessages.length < 2) return null;

  const scrollToMessage = (index: number) => {
    const el = document.getElementById(`msg-${index}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  return (
    <div className="hidden w-12 shrink-0 border-l bg-muted/10 md:block">
      <ScrollArea className="h-full">
        <div className="flex flex-col items-center gap-1 p-1 pt-2">
          {userMessages.map((msg) => (
            <Tooltip key={msg.index}>
              <TooltipTrigger>
                <button
                  onClick={() => scrollToMessage(msg.index)}
                  className="flex h-8 w-8 items-center justify-center rounded-md hover:bg-muted transition-colors"
                >
                  <MessageSquare className="h-3.5 w-3.5 text-muted-foreground" />
                </button>
              </TooltipTrigger>
              <TooltipContent side="left" className="max-w-[220px]">
                <p className="text-xs line-clamp-3">{msg.content}</p>
              </TooltipContent>
            </Tooltip>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
