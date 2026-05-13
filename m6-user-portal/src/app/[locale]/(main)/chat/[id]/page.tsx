/**
 * Existing conversation page — loads messages by conversation ID.
 *
 * WHY: When the user clicks a conversation in the sidebar, Next.js
 * navigates to /chat/[id]. This page fetches the conversation
 * messages via the API and hydrates the chat store, then renders
 * the same ChatPanel as the new chat page.
 */

'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { ChatPanel } from '@/components/chat/chat-panel';
import { useChatStore } from '@/lib/stores/chat-store';
import { getConversation } from '@/lib/api/conversations';

export default function ConversationPage() {
  const { id } = useParams<{ id: string }>();
  const { loadMessages, clearMessages } = useChatStore();
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    clearMessages();
    getConversation(id)
      .then((res) => {
        loadMessages(res.messages);
        setIsLoaded(true);
      })
      .catch(() => setIsLoaded(true));
    return () => {
      clearMessages();
    };
  }, [id, clearMessages, loadMessages]);

  if (!isLoaded) return null;
  return <ChatPanel />;
}
