/**
 * Right-side slide-out citation details panel.
 *
 * WHY: A pure CSS slide-out panel instead of shadcn/ui Sheet, because
 * the Sheet always renders a backdrop overlay that blurs the main
 * content — unacceptable for a companion reference panel. This
 * implementation slides in from the right without any overlay,
 * keeping the chat area fully visible and interactive.
 *
 * Clicking a citation badge [1] opens the panel. Clicking [2]
 * switches the content without closing. Clicking the X or pressing
 * Escape closes it. The panel width adapts with the viewport.
 */

'use client';

import { useEffect, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { useChatStore } from '@/lib/stores/chat-store';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { X } from 'lucide-react';

export function CitationPanel() {
  const t = useTranslations();
  const citations = useChatStore((s) => s.citations);
  const selectedIndex = useChatStore((s) => s.selectedCitationIndex);
  const setSelectedCitation = useChatStore((s) => s.setSelectedCitationIndex);

  const open = selectedIndex !== null;

  // Close on Escape key
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') setSelectedCitation(null);
    },
    [setSelectedCitation],
  );

  useEffect(() => {
    if (open) document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [open, handleKeyDown]);

  if (!open) return null;

  return (
    <>
      {/* Slide-out panel — no overlay, no blur */}
      <div
        data-slot="citation-panel"
        className={
          'fixed inset-y-0 right-0 z-40 w-[380px] sm:w-[440px] ' +
          'flex flex-col border-l bg-background shadow-xl ' +
          'animate-in slide-in-from-right duration-200'
        }
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="font-semibold text-sm">{t('chat.citation.title')}</h2>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            onClick={() => setSelectedCitation(null)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Scrollable citation list */}
        <ScrollArea className="flex-1">
          {citations.length === 0 ? (
            <p className="p-4 text-sm text-muted-foreground">
              {t('chat.citation.noReferences')}
            </p>
          ) : (
            <div className="space-y-4 p-4">
              {citations.map((c) => (
                <div
                  key={c.index}
                  className={`rounded-lg border p-4 transition-colors ${
                    c.index === selectedIndex
                      ? 'border-primary bg-primary/5'
                      : ''
                  }`}
                >
                  <p className="font-semibold text-sm whitespace-normal break-words">
                    [{c.index}] {c.source_doc}
                  </p>
                  <p className="mt-1.5 text-sm text-muted-foreground whitespace-normal break-words">
                    {c.section}
                  </p>
                  {c.clause_id && (
                    <p className="mt-1.5 font-mono text-xs bg-muted px-2 py-0.5 rounded inline-block whitespace-normal break-all">
                      {c.clause_id}
                    </p>
                  )}
                  {c.excerpt && (
                    <blockquote className="mt-3 border-l-2 pl-3 text-xs italic text-muted-foreground whitespace-normal break-words">
                      {c.excerpt}
                    </blockquote>
                  )}
                  {c.url && (
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-block text-xs text-primary underline break-all"
                    >
                      {t('chat.citation.viewSource')}
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>
    </>
  );
}
