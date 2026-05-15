/**
 * Right-side citation panel — third column in AppLayout.
 *
 * WHY: This is a companion panel that slides in as a column, NOT an
 * overlay. The AppLayout controls the column width; this component
 * fills it. When no citation is selected, the column is 0-width
 * and this component's content is hidden by overflow-hidden on the
 * parent. This design ensures the main content area is never
 * obscured or blurred.
 *
 * Clicking [1] opens the panel. Clicking [2] switches the highlighted
 * citation. Click X or press Escape to close.
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
    <div data-slot="citation-panel" className="flex h-full w-[420px] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3 shrink-0">
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
  );
}
