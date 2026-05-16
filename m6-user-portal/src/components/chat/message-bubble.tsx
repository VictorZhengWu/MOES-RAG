/**
 * A single chat message bubble with Markdown rendering and citation badges.
 *
 * WHY: Each message needs distinct styling for user vs assistant and
 * Markdown rendering for AI responses. Citations appear as clickable
 * numbered badges [1] [2] — clicking opens the CitationPanel sheet
 * on the right side via chatStore.setSelectedCitationIndex.
 */

'use client';

import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';
import type { Message, Citation } from '@/types';
import { useChatStore } from '@/lib/stores/chat-store';
import { Badge } from '@/components/ui/badge';
import { FileText } from 'lucide-react';

interface Props {
  message: Message;
  messageIndex: number;
  citations?: Citation[];
  isStreaming?: boolean;
}

export function MessageBubble({
  message,
  messageIndex,
  citations,
  isStreaming,
}: Props) {
  const isUser = message.role === 'user';
  const setSelectedCitation = useChatStore((s) => s.setSelectedCitationIndex);

  return (
    <div
      id={`msg-${messageIndex}`}
      className="flex w-full py-3"
      style={{
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        paddingLeft: isUser ? undefined : '10%',
        paddingRight: isUser ? '10%' : undefined,
      }}
    >
      <div
        className={cn(
          'max-w-[70%] rounded-2xl px-4 py-3',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-muted',
        )}
      >
        {isUser ? (
          <>
            {/* File attachments with icons */}
            {message.attachments && message.attachments.length > 0 && (
              <div className="mb-2 space-y-1">
                {message.attachments.map((file, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 rounded-md bg-white/10 px-3 py-1.5 text-xs"
                  >
                    <FileText className="h-3.5 w-3.5 shrink-0 opacity-70" />
                    <span className="truncate">{file.name}</span>
                  </div>
                ))}
              </div>
            )}
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          </>
        ) : (
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {/* Streaming cursor */}
        {isStreaming && (
          <span className="ml-1 inline-block h-4 w-1 animate-pulse bg-current" />
        )}

        {/* Citation badges — click opens right-side CitationPanel */}
        {citations && citations.length > 0 && !isUser && (
          <div className="mt-3 flex flex-wrap gap-1.5 border-t pt-2">
            {citations.map((c) => (
              <Badge
                key={c.index}
                variant="secondary"
                className="cursor-pointer text-xs hover:bg-secondary/80 transition-colors"
                onClick={() => setSelectedCitation(c.index)}
              >
                [{c.index}] {c.source_doc.split(' ').slice(0, 2).join(' ')}
              </Badge>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
