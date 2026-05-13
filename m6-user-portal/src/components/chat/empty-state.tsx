/**
 * Empty state shown when no conversation is active.
 * Displays the app name, subtitle, and 5 example questions.
 *
 * WHY: Gives first-time users immediate guidance on what they can ask.
 * Clicking a suggestion starts a chat directly, reducing friction.
 */

'use client';

import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { useChatStream } from '@/lib/hooks/use-chat-stream';

export function EmptyState() {
  const t = useTranslations();
  const { startStream } = useChatStream();

  const handleSuggestion = async (text: string) => {
    await startStream(
      {
        model: 'marine-rag-mock',
        messages: [{ role: 'user', content: text }],
      },
      true, // startFresh
    );
  };

  const suggestions = t.raw('chat.empty.suggestions.items') as string[];

  return (
    <div className="flex flex-1 flex-col items-center justify-center px-4">
      <h1 className="text-2xl font-bold">{t('chat.empty.title')}</h1>
      <p className="mt-2 text-muted-foreground">{t('chat.empty.subtitle')}</p>
      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        {Array.isArray(suggestions) &&
          suggestions.map((text: string, i: number) => (
            <Button
              key={i}
              variant="outline"
              className="h-auto justify-start px-4 py-3 text-left text-sm"
              onClick={() => handleSuggestion(text)}
            >
              {text}
            </Button>
          ))}
      </div>
    </div>
  );
}
