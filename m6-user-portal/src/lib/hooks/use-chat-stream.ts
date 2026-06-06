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

import { useCallback } from 'react';
import { useChatStore } from '@/lib/stores/chat-store';
import { useAuthStore } from '@/lib/stores/auth-store';
import { streamChat } from '@/lib/api/chat';
import type { ChatRequest, Citation } from '@/types';

// Module-level ref so ALL hook instances share the same controller.
// Fixes: stop button only works for messages from the same component
const sharedAbortRef = { current: null as AbortController | null };

export function useChatStream() {
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
      sharedAbortRef.current = controller;

      try {
        const token = useAuthStore.getState().token ?? undefined;
        const body = await streamChat(request, token, controller.signal);
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
            } catch (err) {
              if ((err as Error).name === 'AbortError') throw err;
              // Ignore malformed JSON chunks
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
    sharedAbortRef.current?.abort();
  }, []);

  return { startStream, stopStream };
}
