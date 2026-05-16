/**
 * Jump navigation — unified lines + listbox on the right edge.
 *
 * Two visual states:
 *   Closed: only thin gray/blue lines, fixed-positioned, vertically centered.
 *   Open (hover): a popover box extends to the LEFT with text rows. The
 *     lines are embedded in the box's right edge. Text and lines form one
 *     unified component. Each row has text + line, center-aligned.
 *
 * - Listbox is narrow — text ends close to the lines.
 * - Thin custom scrollbar appears to the right of the lines when needed.
 * - Mouse wheel in the area scrolls the listbox content (not the page).
 * - Lines and text rows scroll together as one unit.
 */

'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useChatStore } from '@/lib/stores/chat-store';

const LINE_WIDTH = 18;          // px — wider hit area for the thin line
const LINE_HEIGHT = 2;          // px — visual thickness of the line
const ROW_HEIGHT = 30;          // px — height of each text+line row
const MAX_VISIBLE = 10;         // max rows before scrollbar appears
const FIXED_RIGHT = 16;         // px from right viewport edge
const BOX_WIDTH = 200;          // px — text area width (narrow)
const SCROLLBAR_WIDTH = 4;      // px — thin scrollbar

// Colors
const BLUE = 'rgba(129,140,248,0.8)';
const GRAY = 'rgba(156,163,175,0.25)';

function shortPreview(text: string, maxLen = 12): string {
  const cleaned = text.replace(/\s+/g, ' ').trim();
  return cleaned.length > maxLen ? cleaned.slice(0, maxLen) + '...' : cleaned;
}

export function JumpNavigation() {
  const messages = useChatStore((s) => s.messages);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [showBox, setShowBox] = useState(false);
  const [activeIndex, setActiveIndex] = useState<number | null>(null);
  const listRef = useRef<HTMLDivElement>(null);

  const userQs = messages
    .map((msg, i) => ({ index: i, content: msg.content }))
    .filter((m) => messages[m.index]?.role === 'user');

  const getScrollContainer = useCallback(
    () => document.getElementById('chat-scroll-container') as HTMLDivElement | null,
    [],
  );

  // Track which question is currently visible in the viewport
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

  // Scroll wheel in this area scrolls the list (not the page)
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (showBox && listRef.current) {
      listRef.current.scrollBy({ top: e.deltaY, behavior: 'auto' });
    }
  }, [showBox]);

  if (userQs.length < 2) return null;

  const numRows = userQs.length;
  const totalHeight = numRows * ROW_HEIGHT;
  const showScrollbar = numRows > MAX_VISIBLE;
  // The visible area is capped at MAX_VISIBLE rows when scrollable
  const boxHeight = Math.min(numRows, MAX_VISIBLE) * ROW_HEIGHT;

  const scrollToMessage = (index: number) => {
    const el = document.getElementById(`msg-${index}`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      el.style.transition = 'background-color 0.3s';
      el.style.backgroundColor = 'rgba(129,140,248,0.06)';
      setTimeout(() => { el.style.backgroundColor = ''; }, 2000);
    }
  };

  const handleMouseEnter = () => setShowBox(true);
  const handleMouseLeave = () => {
    setShowBox(false);
    setHoveredIndex(null);
  };

  // The entire component width: text area + gap + line area + (optional scrollbar)
  const totalWidth = BOX_WIDTH + 8 + LINE_WIDTH + (showScrollbar ? SCROLLBAR_WIDTH + 4 : 0);

  return (
    <div
      className="fixed flex items-center justify-center z-10"
      style={{ right: FIXED_RIGHT, top: 44, bottom: 0 }}
    >
      {/* Unified box: text (left) + lines (right) + optional thin scrollbar */}
      {showBox ? (
        <div
          className="relative flex rounded-xl border bg-popover shadow-2xl pointer-events-auto"
          style={{ height: boxHeight, width: totalWidth }}
          onWheel={handleWheel}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          {/* Text column — native scrollbar hidden, uses custom thin one on right */}
          <div
            ref={listRef}
            className="overflow-y-auto flex-1 [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden"
            style={{ width: BOX_WIDTH, maxHeight: boxHeight }}
            onWheel={handleWheel}
          >
            {/* Inner div with full height for scrolling */}
            <div style={{ height: totalHeight }}>
              {userQs.map((q) => {
                const isActive = q.index === activeIndex;
                const isHovered = q.index === hoveredIndex;
                return (
                  <button
                    key={q.index}
                    onClick={() => scrollToMessage(q.index)}
                    onMouseEnter={() => setHoveredIndex(q.index)}
                    onMouseLeave={() => setHoveredIndex(null)}
                    className="w-full text-left px-2 text-xs transition-colors hover:bg-muted/50 flex items-center outline-none"
                    style={{
                      height: ROW_HEIGHT,
                      color: isHovered || isActive
                        ? 'rgba(79,70,229,0.95)'
                        : 'rgba(107,114,128,0.7)',
                      fontWeight: isHovered || isActive ? 500 : 400,
                    }}
                  >
                    {shortPreview(q.content)}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Gap + line column */}
          <div className="flex flex-col items-center justify-center" style={{ width: LINE_WIDTH + 8 }}>
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
                    height: ROW_HEIGHT,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <span
                    className="rounded-full"
                    style={{
                      width: LINE_WIDTH - 4,
                      height: LINE_HEIGHT,
                      backgroundColor: isHovered || isActive ? BLUE : GRAY,
                    }}
                  />
                </button>
              );
            })}
          </div>

          {/* Thin scrollbar track — to the right of the lines */}
          {showScrollbar && (
            <div className="relative" style={{ width: SCROLLBAR_WIDTH + 2 }}>
              <div
                className="absolute inset-y-0 rounded-full bg-muted-foreground/10"
                style={{ width: SCROLLBAR_WIDTH, right: 0 }}
              >
                <div
                  className="absolute rounded-full bg-muted-foreground/30"
                  style={{
                    width: SCROLLBAR_WIDTH,
                    height: `${(MAX_VISIBLE / numRows) * 100}%`,
                    top: `${(listRef.current?.scrollTop || 0) / totalHeight * 100}%`,
                    minHeight: 16,
                  }}
                />
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Closed state: only lines, centered. Mouse events on the lines container. */
        <div
          className="flex flex-col items-center pointer-events-auto"
          style={{ gap: `${ROW_HEIGHT - LINE_HEIGHT}px`, height: totalHeight, justifyContent: 'center' }}
          onWheel={handleWheel}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          {userQs.map((q) => {
            const isActive = q.index === activeIndex;
            return (
              <button
                key={q.index}
                onClick={() => scrollToMessage(q.index)}
                className="shrink-0 rounded-full transition-colors duration-150"
                style={{
                  width: LINE_WIDTH - 4,
                  height: LINE_HEIGHT,
                  backgroundColor: isActive ? BLUE : GRAY,
                }}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
