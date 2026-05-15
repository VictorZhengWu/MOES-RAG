/**
 * Jump navigation — DeepSeek-style thin horizontal lines inside scroll area.
 *
 * Positioned absolutely on the right edge of the scroll container.
 * Each gray line represents one user question. Hover: line turns blue,
 * a floating popup appears to the left showing the full question text.
 * Move mouse away: popup disappears.
 * A blue indicator line tracks which question is currently visible.
 *
 * Lines are distributed along the full scrollable height. Gap between
 * lines is wider (~16px) for easy targeting. No border on the strip.
 */

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useChatStore } from '@/lib/stores/chat-store';

interface Props {
  scrollContainerRef: React.RefObject<HTMLDivElement | null>;
}

export function JumpNavigation({ scrollContainerRef }: Props) {
  const messages = useChatStore((s) => s.messages);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // Extract user question indices
  const userQs = messages
    .map((msg, i) => ({ index: i, content: msg.content }))
    .filter((m) => messages[m.index]?.role === 'user');

  // Track which question is currently visible (nearest to viewport top)
  const updateActive = useCallback(() => {
    if (userQs.length === 0) return;
    const container = scrollContainerRef.current;
    if (!container) return;
    const containerRect = container.getBoundingClientRect();
    const viewTop = containerRect.top + 80; // offset from top

    let closest = userQs[0].index;
    let minDist = Infinity;
    for (const q of userQs) {
      const el = document.getElementById(`msg-${q.index}`);
      if (!el) continue;
      const rect = el.getBoundingClientRect();
      const dist = Math.abs(rect.top - viewTop);
      if (dist < minDist) { minDist = dist; closest = q.index; }
    }
    setActiveIndex(closest);
  }, [userQs, scrollContainerRef]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    container.addEventListener('scroll', updateActive, { passive: true });
    updateActive();
    return () => container.removeEventListener('scroll', updateActive);
  }, [updateActive, scrollContainerRef]);

  // Don't show for single-question chats
  if (userQs.length < 2) return null;

  // Calculate vertical positions: distribute lines evenly within
  // the container height, padded top and bottom so they're centered
  const totalLines = userQs.length;
  const paddingPx = 32;
  const availablePct = 100 - (paddingPx * 2 / (scrollContainerRef.current?.scrollHeight || 1000)) * 100;
  const stepPct = Math.max(availablePct / (totalLines - 1), 6);

  const scrollToMessage = (index: number) => {
    const el = document.getElementById(`msg-${index}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      el.style.transition = 'background-color 0.3s';
      el.style.backgroundColor = 'var(--color-accent, rgba(99,102,241,0.08))';
      setTimeout(() => { el.style.backgroundColor = ''; }, 2000);
    }
  };

  return (
    <div
      ref={containerRef}
      className="absolute right-1 top-0 bottom-0 w-6 flex flex-col items-center pointer-events-none"
      style={{ paddingTop: `${paddingPx}px`, paddingBottom: `${paddingPx}px`, justifyContent: 'space-between' }}
    >
      {userQs.map((q, i) => {
        const isActive = q.index === activeIndex;
        const isHovered = q.index === hoveredIndex;
        return (
          <div key={q.index} className="relative flex items-center justify-center pointer-events-auto">
            {/* The line */}
            <button
              onClick={() => scrollToMessage(q.index)}
              onMouseEnter={() => setHoveredIndex(q.index)}
              onMouseLeave={() => setHoveredIndex(null)}
              className="w-6 h-[3px] rounded-full transition-colors duration-150"
              style={{
                backgroundColor: isActive ? 'var(--color-primary, #6366f1)' : 'rgba(156,163,175,0.3)',
              }}
              title={q.content.slice(0, 60)}
            />

            {/* Floating popup on hover */}
            {isHovered && (
              <div className="absolute right-full mr-2 top-1/2 -translate-y-1/2 z-50 pointer-events-none">
                <div className="whitespace-nowrap rounded-lg border bg-popover px-3 py-2 text-sm text-popover-foreground shadow-lg max-w-[320px]">
                  <p className="line-clamp-4 whitespace-normal">{q.content}</p>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
