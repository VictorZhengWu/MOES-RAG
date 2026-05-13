/**
 * Chat panel: combines message list + input bar.
 * Shows EmptyState when no messages, MessageList + ChatInput otherwise.
 */

'use client';

import { MessageList } from './message-list';
import { ChatInput } from './chat-input';
import { EmptyState } from './empty-state';
import { useChatStore } from '@/lib/stores/chat-store';

export function ChatPanel() {
  const messages = useChatStore((s) => s.messages);

  return (
    <div className="flex h-full flex-col">
      {messages.length === 0 ? <EmptyState /> : <MessageList />}
      <ChatInput />
    </div>
  );
}
