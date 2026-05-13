/**
 * Right-side slide-out citation details panel.
 *
 * WHY: Replaces the old per-citation popover design. When the user
 * clicks a citation badge [1], this panel slides in from the right
 * showing the full source document name, section, clause ID, and
 * excerpt. All citations from the current answer are scrollable.
 * Uses shadcn/ui Sheet component positioned on the right side.
 *
 * The open state is driven by chatStore.selectedCitationIndex !== null.
 */

'use client';

import { useTranslations } from 'next-intl';
import { useChatStore } from '@/lib/stores/chat-store';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';
import { ScrollArea } from '@/components/ui/scroll-area';

export function CitationPanel() {
  const t = useTranslations();
  const citations = useChatStore((s) => s.citations);
  const selectedIndex = useChatStore((s) => s.selectedCitationIndex);
  const setSelectedCitation = useChatStore((s) => s.setSelectedCitationIndex);

  const open = selectedIndex !== null;
  const selectedCitation = citations.find((c) => c.index === selectedIndex);

  return (
    <Sheet open={open} onOpenChange={(o) => !o && setSelectedCitation(null)}>
      <SheetContent side="right" className="w-[400px] sm:w-[480px]">
        <SheetHeader>
          <SheetTitle>{t('chat.citation.title')}</SheetTitle>
        </SheetHeader>
        <ScrollArea className="mt-4 h-[calc(100vh-120px)]">
          {citations.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t('chat.citation.noReferences')}
            </p>
          ) : (
            <div className="space-y-6">
              {citations.map((c) => (
                <div
                  key={c.index}
                  className={`rounded-lg border p-4 transition-colors ${
                    c.index === selectedIndex
                      ? 'border-primary bg-primary/5'
                      : ''
                  }`}
                >
                  <p className="font-semibold text-sm">
                    [{c.index}] {c.source_doc}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {c.section}
                  </p>
                  {c.clause_id && (
                    <p className="mt-1 font-mono text-xs bg-muted px-2 py-0.5 rounded inline-block">
                      {c.clause_id}
                    </p>
                  )}
                  {c.excerpt && (
                    <blockquote className="mt-3 border-l-2 pl-3 text-xs italic text-muted-foreground">
                      {c.excerpt}
                    </blockquote>
                  )}
                  {c.url && (
                    <a
                      href={c.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-block text-xs text-primary underline"
                    >
                      {t('chat.citation.viewSource')}
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
