/**
 * Jump navigation — DeepSeek-style thin horizontal lines on the right edge.
 *
 * Spec:
 * 1. Lines always spaced 25px apart, centered vertically in the viewport.
 * 2. When mouse is away: only gray lines visible, nothing else.
 * 3. Hover over the line area → a floating listbox appears showing user
 *    questions (max 10 chars + "..."). The hovered line turns blue.
 *    Click scrolls to that question.
 * 4. If many questions, listbox shows max 10 scrollable rows.
 * 5. Mouse leaves → listbox disappears, lines revert to gray.
 * 6. As content scrolls, the line for the currently visible question
 *    turns blue; others stay gray.
 */

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useChatStore } from '@/lib/stores/chat-store';

const LINE_GAP = 25;          // px between consecutive lines
const LINE_WIDTH = 22;        // px
const LINE_HEIGHT = 3;        // px
const MAX_LISTBOX_ITEMS = 10; // max rows in popup listbox

interface Props {
  scrollContainerRef: React.RefObject<HTMLDivElement | null>;
}

function shortPreview(text: string, maxLen = 10): string {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  return cleaned.length > maxLen ? cleaned.slice(0, maxLen) + '...' : cleaned;
}

export function JumpNavigation({ scrollContainerRef }: Props) {
  const messages = useChatStore((s) => s.messages);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [showListbox, setShowListbox] = useState(false);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Extract user question indices from messages
  const userQs = messages
    .map((msg, i) => ({ index: i, content: msg.content }))
    .filter((m) => messages[m.index]?.role === 'user');

  // Track which question is currently visible
  const updateActive = useCallback(() => {
    if (userQs.length === 0) return;
    const container = scrollContainerRef.current;
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const viewCenter = rect.top + rect.height / 2;

    let closest = userQs[0].index;
    let minDist = Infinity;
    for (const q of userQs) {
      const el = document.getElementById(`msg-${q.index}`);
      if (!el) continue;
      const qRect = el.getBoundingClientRect();
      const qCenter = qRect.top + qRect.height / 2;
      const dist = Math.abs(qCenter - viewCenter);
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

  if (userQs.length < 2) return null;

  const totalHeight = (userQs.length - 1) * LINE_GAP;

  const scrollToMessage = (index: number) => {
    const el = document.getElementById(`msg-${index}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      el.style.transition = 'background-color 0.3s';
      el.style.backgroundColor = 'rgba(99,102,241,0.06)';
      setTimeout(() => { el.style.backgroundColor = ''; }, 2000);
    }
  };

  const handleMouseEnterStrip = () => setShowListbox(true);
  const handleMouseLeaveStrip = () => {
    setShowListbox(false);
    setHoveredIndex(null);
  };

  return (
    <div
      ref={containerRef}
      className="absolute right-1 top-0 bottom-0 w-6 flex flex-col items-center justify-center pointer-events-none z-10"
      onMouseEnter={handleMouseEnterStrip}
      onMouseLeave={handleMouseLeaveStrip}
    >
      {/* Invisible hit area to make hovering easier */}
      <div className="absolute inset-0 pointer-events-auto" />

      {/* Lines container — centered vertically */}
      <div
        className="relative flex flex-col items-center pointer-events-auto"
        style={{ height: totalHeight, gap: `${LINE_GAP - LINE_HEIGHT}px` }}
      >
        {userQs.map((q) => {
          const isActive = q.index === activeIndex;
          const isHovered = q.index === hoveredIndex;
          return (
            <button
              key={q.index}
              onClick={() => scrollToMessage(q.index)}
              onMouseEnter={() => setHoveredIndex(q.index)}
              onMouseLeave={() => setHoveredIndex(null)}
              className="shrink-0 rounded-full transition-colors duration-150 relative"
              style={{
                width: LINE_WIDTH,
                height: LINE_HEIGHT,
                backgroundColor: isHovered
                  ? 'var(--color-primary, #6366f1)'
                  : isActive
                    ? 'var(--color-primary, #6366f1)'
                    : 'rgba(156,163,175,0.35)',
              }}
            />
          );
        })}
      </div>

      {/* Floating listbox on hover */}
      {showListbox && (
        <div
          className="absolute right-full mr-3 top-1/2 -translate-y-1/2 pointer-events-auto z-50"
          onMouseEnter={() => setShowListbox(true)}
          onMouseLeave={handleMouseLeaveStrip}
        >
          <div
            className="rounded-xl border bg-popover shadow-2xl overflow-hidden"
            style={{ maxHeight: `${MAX_LISTBOX_ITEMS * 36 + 8}px`, width: '280px' }}
          >
            <div
              className="overflow-y-auto max-h-full"
              style={{ maxHeight: `${MAX_LISTBOX_ITEMS * 36 + 8}px` }}
            >
              {userQs.map((q) => (
                <button
                  key={q.index}
                  onClick={() => scrollToMessage(q.index)}
                  onMouseEnter={() => setHoveredIndex(q.index)}
                  className={`w-full text-left px-3 py-2 text-sm transition-colors hover:bg-muted ${
                    q.index === activeIndex ? 'text-primary font-medium' : 'text-foreground'
                  }`}
                >
                  {shortPreview(q.content)}
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
