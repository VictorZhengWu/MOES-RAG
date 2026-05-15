/**
 * Jump navigation — fixed-position thin horizontal lines on the right edge.
 *
 * Spec:
 * - Lines always centered vertically in the viewport (fixed positioning)
 * - 25px gap, light gray by default, lighter blue when active/hovered
 * - Listbox wraps the lines area: when mouse enters the strip, the listbox
 *   appears as an extension to the left, containing question text rows that
 *   align horizontally with their corresponding lines
 * - Hovering a text row makes both the row AND its line blue
 * - Mouse wheel in the line area passes through to scroll the page
 * - Mouse can freely move between lines and listbox text without closing
 */

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useChatStore } from '@/lib/stores/chat-store';

const LINE_GAP = 25;           // px between consecutive lines
const LINE_WIDTH = 20;         // px
const LINE_HEIGHT = 3;         // px
const LISTBOX_WIDTH = 280;     // px
const MAX_LISTBOX_ITEMS = 10;
const FIXED_RIGHT = 16;        // px from right edge (moved left to avoid scrollbar)
const ROW_HEIGHT = 34;         // px per text row in listbox

// Lighter blue
const BLUE_ACTIVE = 'rgba(129,140,248,0.85)';
const BLUE_HOVER = 'rgba(129,140,248,0.85)';
const GRAY = 'rgba(156,163,175,0.3)';

function shortPreview(text: string, maxLen = 10): string {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  return cleaned.length > maxLen ? cleaned.slice(0, maxLen) + '...' : cleaned;
}

export function JumpNavigation() {
  const messages = useChatStore((s) => s.messages);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [showListbox, setShowListbox] = useState(false);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  const userQs = messages
    .map((msg, i) => ({ index: i, content: msg.content }))
    .filter((m) => messages[m.index]?.role === 'user');

  const getScrollContainer = useCallback(
    () => document.getElementById('chat-scroll-container') as HTMLDivElement | null,
    [],
  );

  const updateActive = useCallback(() => {
    if (userQs.length === 0) return;
    const container = getScrollContainer();
    if (!container) return;
    const rect = container.getBoundingClientRect();
    const viewCenter = rect.top + rect.height / 2;
    let closest = userQs[0].index;
    let minDist = Infinity;
    for (const q of userQs) {
      const el = document.getElementById(`msg-${q.index}`);
      if (!el) continue;
      const qRect = el.getBoundingClientRect();
      const dist = Math.abs(qRect.top + qRect.height / 2 - viewCenter);
      if (dist < minDist) { minDist = dist; closest = q.index; }
    }
    setActiveIndex(closest);
  }, [userQs, getScrollContainer]);

  useEffect(() => {
    const container = getScrollContainer();
    if (!container) return;
    container.addEventListener('scroll', updateActive, { passive: true });
    updateActive();
    return () => container.removeEventListener('scroll', updateActive);
  }, [updateActive, getScrollContainer]);

  // Pass mouse wheel through to the scroll container
  const handleWheel = useCallback((e: React.WheelEvent) => {
    const container = getScrollContainer();
    if (container) {
      container.scrollBy({ top: e.deltaY, behavior: 'auto' });
    }
  }, [getScrollContainer]);

  if (userQs.length < 2) return null;

  const totalHeight = (userQs.length - 1) * LINE_GAP;

  const scrollToMessage = (index: number) => {
    const el = document.getElementById(`msg-${index}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      el.style.transition = 'background-color 0.3s';
      el.style.backgroundColor = 'rgba(129,140,248,0.06)';
      setTimeout(() => { el.style.backgroundColor = ''; }, 2000);
    }
  };

  const handleMouseEnter = () => setShowListbox(true);
  const handleMouseLeave = () => {
    setShowListbox(false);
    setHoveredIndex(null);
  };

  // Compute listbox height: min(MAX_LISTBOX_ITEMS, userQs.length) rows
  const listboxRows = Math.min(MAX_LISTBOX_ITEMS, userQs.length);
  const listboxHeight = listboxRows * ROW_HEIGHT + 8;

  return (
    <div
      className="fixed top-0 bottom-0 flex flex-col items-center justify-center pointer-events-none z-10"
      style={{ right: `${FIXED_RIGHT}px` }}
      onWheel={handleWheel}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {/* Invisible hit area for mouse detection */}
      <div
        className="absolute pointer-events-auto"
        style={{
          right: -4,
          top: '50%',
          transform: 'translateY(-50%)',
          width: showListbox ? LISTBOX_WIDTH + LINE_WIDTH + 12 : LINE_WIDTH + 8,
          height: Math.max(totalHeight + 12, 40),
          marginTop: -(totalHeight / 2) - 6,
        }}
      />

      {/* Lines + listbox wrapper */}
      <div className="relative pointer-events-auto" style={{ height: totalHeight }}>
        {/* Listbox — positioned to the LEFT of the lines */}
        {showListbox && (
          <div
            className="absolute top-1/2 -translate-y-1/2 rounded-xl border bg-popover shadow-2xl overflow-hidden pointer-events-auto"
            style={{
              right: LINE_WIDTH + 10,
              width: LISTBOX_WIDTH,
              maxHeight: listboxHeight,
            }}
          >
            <div className="overflow-y-auto" style={{ maxHeight: listboxHeight }}>
              {userQs.map((q) => (
                <button
                  key={q.index}
                  onClick={() => scrollToMessage(q.index)}
                  onMouseEnter={() => setHoveredIndex(q.index)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  className={`w-full text-left px-3 text-sm transition-colors hover:bg-muted ${
                    q.index === hoveredIndex
                      ? 'text-primary font-medium'
                      : q.index === activeIndex
                        ? 'text-primary'
                        : 'text-foreground'
                  }`}
                  style={{ height: ROW_HEIGHT, lineHeight: `${ROW_HEIGHT}px` }}
                >
                  {shortPreview(q.content)}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Lines — centered vertically */}
        <div
          className="flex flex-col items-center h-full"
          style={{ gap: `${LINE_GAP - LINE_HEIGHT}px` }}
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
                className="shrink-0 rounded-full transition-colors duration-150"
                style={{
                  width: LINE_WIDTH,
                  height: LINE_HEIGHT,
                  backgroundColor: isHovered || isActive ? BLUE_ACTIVE : GRAY,
                }}
              />
            );
          })}
        </div>
      </div>
    </div>
  );
}
