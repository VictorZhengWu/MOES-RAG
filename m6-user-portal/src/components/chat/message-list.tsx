/**
 * Scrollable message list.
 */

'use client';

import { useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import { useChatStore } from '@/lib/stores/chat-store';
import { useChatStream } from '@/lib/hooks/use-chat-stream';
import { MessageBubble } from './message-bubble';
import { FollowUpSuggestions } from './follow-up-suggestions';

export interface MessageListHandle {
  scrollContainer: HTMLDivElement | null;
}

export const MessageList = forwardRef<MessageListHandle>(function MessageList(_props, ref) {
  const messages = useChatStore((s) => s.messages);
  const citations = useChatStore((s) => s.citations);
  const isStreaming = useChatStore((s) => s.isStreaming);
  const { startStream } = useChatStream();
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useImperativeHandle(ref, () => ({
    scrollContainer: scrollRef.current,
  }));

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const lastMsg = messages[messages.length - 1];
  const showFollowUps = !isStreaming && lastMsg?.role === 'assistant' && messages.length >= 2;

  const handleFollowUp = async (question: string) => {
    await startStream({
      model: 'marine-rag-mock',
      messages: [...messages, { role: 'user', content: question }],
    });
  };

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
        {showFollowUps && <FollowUpSuggestions onSelect={handleFollowUp} />}
        <div ref={bottomRef} />
      </div>
    </div>
  );
});
