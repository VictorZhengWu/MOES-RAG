/**
 * Scrollable message list with auto-scroll to bottom on new messages.
 *
 * WHY: Chat UX requires automatic scrolling when new messages arrive
 * (especially during streaming). useRef + scrollIntoView is simpler
 * and more reliable than scroll event listeners. Each message gets
 * an id="msg-{index}" for jump-navigation targeting.
 */

'use client';

import { useEffect, useRef } from 'react';
import { useChatStore } from '@/lib/stores/chat-store';
import { MessageBubble } from './message-bubble';

export function MessageList() {
  const messages = useChatStore((s) => s.messages);
  const citations = useChatStore((s) => s.citations);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto px-4">
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
  );
}
