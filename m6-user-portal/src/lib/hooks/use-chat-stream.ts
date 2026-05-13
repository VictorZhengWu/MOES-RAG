/**
 * Hook for handling SSE streaming chat responses.
 *
 * WHY: The browser Fetch API's ReadableStream with SSE parsing is
 * more reliable than EventSource (which can't POST). This hook
 * handles the full lifecycle: connect, parse SSE chunks token-by-token,
 * and clean up properly. Citations are extracted from the final
 * non-streaming-style response (the mock server returns them inline
 * with the last chunk or the final response metadata).
 */

'use client';

import { useCallback, useRef } from 'react';
import { useChatStore } from '@/lib/stores/chat-store';
import { streamChat } from '@/lib/api/chat';
import type { ChatRequest, Citation } from '@/types';

export function useChatStream() {
  const abortRef = useRef<AbortController | null>(null);
  const {
    addMessage,
    appendToLastMessage,
    setCitations,
    setStreaming,
    setLoading,
    clearMessages,
  } = useChatStore();

  const startStream = useCallback(
    async (request: ChatRequest, startFresh = false) => {
      if (startFresh) clearMessages();

      // Add user message immediately (optimistic UI)
      const userMsg = request.messages[request.messages.length - 1];
      if (userMsg && userMsg.role === 'user') {
        addMessage(userMsg);
      }

      setLoading(true);
      setStreaming(true);

      // Create abort controller for cancellation
      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const body = await streamChat(request);
        const reader = body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith('data: ')) continue;
            const data = trimmed.slice(6).trim();
            if (data === '[DONE]') break;

            try {
              const chunk = JSON.parse(data);
              const content = chunk.choices?.[0]?.delta?.content;
              if (content) {
                appendToLastMessage(content);
              }
              // Check for citations in the chunk (extended OpenAI format)
              if (chunk.citations) {
                setCitations(chunk.citations as Citation[]);
              }
            } catch {
              // Ignore malformed JSON chunks (edge case in streaming)
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== 'AbortError') {
          throw err;
        }
      } finally {
        setStreaming(false);
        setLoading(false);
      }
    },
    [addMessage, appendToLastMessage, setCitations, setStreaming, setLoading, clearMessages],
  );

  const stopStream = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { startStream, stopStream };
}
