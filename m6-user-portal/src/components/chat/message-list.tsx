/**
 * Scrollable message list.
 */

'use client';

import { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import { useChatStore } from '@/lib/stores/chat-store';
import { MessageBubble } from './message-bubble';

export interface MessageListHandle {
  scrollContainer: HTMLDivElement | null;
}

export const MessageList = forwardRef<MessageListHandle>(function MessageList(_props, ref) {
  const messages = useChatStore((s) => s.messages);
  const citations = useChatStore((s) => s.citations);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useImperativeHandle(ref, () => ({
    scrollContainer: scrollRef.current,
  }));

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div id="chat-scroll-container" ref={scrollRef} className="flex-1 overflow-y-auto">
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
    </div>
  );
});
