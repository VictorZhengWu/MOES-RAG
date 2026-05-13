/**
 * Chat completion API functions.
 *
 * WHY: Separating chat API calls from UI components means the components
 * don't need to know HTTP details. The useChatStream hook calls
 * streamChat() and receives a ReadableStream, while non-streaming
 * can fall back to sendMessage().
 *
 * Streaming uses raw fetch (not apiPost) because the response is a
 * ReadableStream, not JSON.
 */

import type { ChatRequest, ChatResponse } from '@/types';
import { apiPost } from './client';

export async function sendMessage(request: ChatRequest): Promise<ChatResponse> {
  return apiPost<ChatResponse>('/v1/chat/completions', {
    ...request,
    stream: false,
  });
}

export async function streamChat(
  request: ChatRequest,
): Promise<ReadableStream<Uint8Array>> {
  const baseUrl =
    process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';

  const res = await fetch(`${baseUrl}/v1/chat/completions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...request, stream: true }),
  });

  if (!res.ok) {
    throw new Error(`Chat stream failed: ${res.status}`);
  }

  // ReadableStream is non-null for streaming responses from Mock Server
  if (!res.body) {
    throw new Error('No response body in streaming chat');
  }

  return res.body;
}
