/**
 * Right-side jump navigation strip — thin gray horizontal lines.
 *
 * Each line represents one user question in the current chat.
 * Hover: line turns blue, tooltip shows first 12 chars + "..."
 * Click: scrolls to that question in the chat area.
 *
 * Only appears when there are >= 2 user messages.
 *
 * WHY: DeepSeek-style quick navigation. Long conversations need
 * fast random access to earlier questions. Thin lines are
 * unobtrusive; tooltip provides just enough context.
 */

'use client';

import { useChatStore } from '@/lib/stores/chat-store';

function preview(text: string, maxLen = 12): string {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  return cleaned.length > maxLen ? cleaned.slice(0, maxLen) + '...' : cleaned;
}

export function JumpNavigation() {
  const messages = useChatStore((s) => s.messages);

  // Extract user messages with their indices
  const userMessages = messages
    .map((msg, i) => ({ content: msg.content, index: i }))
    .filter((msg) => msg.content.trim().length > 0)
    .filter((_, i, arr) => {
      // Only user messages (every other message starting from index 0)
      return i % 2 === 0 || arr.length <= 2;
    })
    .filter((msg) => {
      // Heuristic: user messages are typically every other message
      // and shorter than assistant responses
      const isProbablyUser =
        messages[msg.index]?.role === 'user' ||
        msg.content.length < 500;
      return isProbablyUser;
    });

  // More reliable: filter by role
  const userQs = messages
    .map((msg, i) => ({ ...msg, index: i }))
    .filter((msg) => msg.role === 'user');

  if (userQs.length < 2) return null;

  const scrollToMessage = (index: number) => {
    const el = document.getElementById(`msg-${index}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      // Brief highlight
      el.style.transition = 'background-color 0.3s';
      el.style.backgroundColor = 'var(--color-accent, rgba(99,102,241,0.1))';
      setTimeout(() => { el.style.backgroundColor = ''; }, 1500);
    }
  };

  return (
    <div className="hidden w-12 shrink-0 border-l bg-muted/5 md:flex flex-col items-center pt-4 gap-2">
      {userQs.map((msg) => (
        <div key={msg.index} className="relative group flex items-center justify-center w-full">
          <button
            onClick={() => scrollToMessage(msg.index)}
            className="w-8 h-[3px] rounded-full bg-muted-foreground/25 hover:bg-primary transition-colors cursor-pointer"
            title={preview(msg.content)}
          />
          {/* Tooltip on hover */}
          <div className="absolute right-full mr-2 top-1/2 -translate-y-1/2 hidden group-hover:block z-50 pointer-events-none">
            <div className="whitespace-nowrap rounded-md bg-popover border px-2.5 py-1.5 text-xs text-popover-foreground shadow-md">
              {preview(msg.content)}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
