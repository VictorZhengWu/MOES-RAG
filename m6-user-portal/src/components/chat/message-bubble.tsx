/**
 * Chat message bubble with Markdown, citations, copy, feedback, and source indicators.
 */

'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';
import type { Message, Citation } from '@/types';
import { useChatStore } from '@/lib/stores/chat-store';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FileText, Copy, Check, ThumbsUp, ThumbsDown } from 'lucide-react';

interface Props {
  message: Message;
  messageIndex: number;
  citations?: Citation[];
  isStreaming?: boolean;
}

export function MessageBubble({ message, messageIndex, citations, isStreaming }: Props) {
  const isUser = message.role === 'user';
  const setSelectedCitation = useChatStore((s) => s.setSelectedCitationIndex);
  const [copied, setCopied] = useState(false);
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      id={`msg-${messageIndex}`}
      className="flex w-full py-3 group"
      style={{
        justifyContent: isUser ? 'flex-end' : 'flex-start',
        paddingLeft: isUser ? undefined : '10%',
        paddingRight: isUser ? '10%' : undefined,
      }}
    >
      <div className={cn('max-w-[70%] rounded-2xl px-4 py-3 relative', isUser ? 'bg-primary text-primary-foreground' : 'bg-muted')}>
        {/* Copy button — visible on hover */}
        <button
          onClick={handleCopy}
          className={cn(
            'absolute top-2 right-2 p-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity',
            isUser ? 'hover:bg-white/20' : 'hover:bg-foreground/10',
          )}
          title="Copy"
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </button>

        {isUser ? (
          <>
            {message.attachments && message.attachments.length > 0 && (
              <div className="mb-2 space-y-1">
                {message.attachments.map((file, i) => (
                  <div key={i} className="flex items-center gap-2 rounded-md bg-white/10 px-3 py-1.5 text-xs">
                    <FileText className="h-3.5 w-3.5 shrink-0 opacity-70" />
                    <span className="truncate">{file.name}</span>
                  </div>
                ))}
              </div>
            )}
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          </>
        ) : (
          <>
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>

            {/* Feedback buttons */}
            {!isStreaming && (
              <div className="flex items-center gap-1 mt-2 pt-2 border-t border-border/30">
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn('h-7 w-7', feedback === 'up' && 'text-green-500')}
                  onClick={() => setFeedback(feedback === 'up' ? null : 'up')}
                >
                  <ThumbsUp className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn('h-7 w-7', feedback === 'down' && 'text-red-500')}
                  onClick={() => setFeedback(feedback === 'down' ? null : 'down')}
                >
                  <ThumbsDown className="h-3.5 w-3.5" />
                </Button>
              </div>
            )}
          </>
        )}

        {isStreaming && (
          <span className="ml-1 inline-block h-4 w-1 animate-pulse bg-current" />
        )}

        {/* Citation badges + source type indicators */}
        {citations && citations.length > 0 && !isUser && (
          <div className="mt-2 flex flex-wrap gap-1.5 border-t pt-2">
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
