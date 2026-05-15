/**
 * Scrollable message list with embedded jump navigation.
 *
 * The jump nav is absolutely positioned along the right edge INSIDE
 * the scroll container, so it scrolls with the content naturally.
 */

'use client';

import { useEffect, useRef } from 'react';
import { useChatStore } from '@/lib/stores/chat-store';
import { MessageBubble } from './message-bubble';
import { JumpNavigation } from '@/components/navigation/jump-navigation';

export function MessageList() {
  const messages = useChatStore((s) => s.messages);
  const citations = useChatStore((s) => s.citations);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div ref={scrollRef} className="flex-1 overflow-y-auto relative">
      <div className="px-4">
        {messages.map((msg, i) => (
          <MessageBubble
            key={i}
            message={msg}
            messageIndex={i}
            citations={msg.role === 'assistant' ? citations : undefined}
            isStreaming={
              isStreaming &&
              i === messages.length - 1 &&
              msg.role === 'assistant'
            }
          />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Jump nav — inside the scroll container, positioned on the right edge */}
      <JumpNavigation scrollContainerRef={scrollRef} />
    </div>
  );
}
