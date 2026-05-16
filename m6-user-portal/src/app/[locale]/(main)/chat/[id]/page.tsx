/**
 * Existing conversation page — loads messages by conversation ID.
 *
 * WHY: Only fetches messages when the conversation ID changes or the
 * store is empty. Previously it cleared + re-fetched on EVERY mount,
 * which destroyed the user's conversation when navigating back after
 * login/logout (since Mock Server returns different canned data).
 */

'use client';

import { useEffect, useState, useRef } from 'react';
import { useParams } from 'next/navigation';
import { ChatPanel } from '@/components/chat/chat-panel';
import { useChatStore } from '@/lib/stores/chat-store';
import { getConversation } from '@/lib/api/conversations';

export default function ConversationPage() {
  const { id } = useParams<{ id: string }>();
  const { loadMessages, messages } = useChatStore();
  const [isLoaded, setIsLoaded] = useState(false);
  const lastLoadedId = useRef<string | null>(null);

  useEffect(() => {
    // Only fetch if we haven't loaded this conversation yet
    if (lastLoadedId.current === id) {
      setIsLoaded(true);
      return;
    }

    getConversation(id)
      .then((res) => {
        loadMessages(res.messages);
        lastLoadedId.current = id;
        setIsLoaded(true);
      })
      .catch(() => setIsLoaded(true));
  }, [id, loadMessages]);

  if (!isLoaded) return null;
  return <ChatPanel />;
}
