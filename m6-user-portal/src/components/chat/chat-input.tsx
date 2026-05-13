/**
 * Chat input bar: textarea + file attachment + web search toggle + send/stop.
 *
 * Layout:
 * ┌─────────────────────────────────────────────────────────┐
 * │ [📎] [_____________________________] [🌐] [Send/■]    │
 * └─────────────────────────────────────────────────────────┘
 *
 * WHY: File attachment and web search toggle are optional augmentations
 * that follow the DeepSeek/ChatGPT UX pattern. All buttons have clear
 * visual states (active/inactive) for accessibility.
 */

'use client';

import { useRef, KeyboardEvent, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Paperclip, Globe } from 'lucide-react';
import { useChatStore } from '@/lib/stores/chat-store';
import { useChatStream } from '@/lib/hooks/use-chat-stream';

export function ChatInput() {
  const t = useTranslations();
  const {
    inputValue,
    setInputValue,
    isLoading,
    isStreaming,
    messages,
    webSearchEnabled,
    toggleWebSearch,
  } = useChatStore();
  const { startStream, stopStream } = useChatStream();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = async () => {
    const content = inputValue.trim();
    if (!content || isLoading) return;
    setInputValue('');

    await startStream({
      model: 'marine-rag-mock',
      messages: [...messages, { role: 'user', content }],
      web_search: webSearchEnabled,
    });
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      // Phase 2: upload file and attach to request. Phase 1: placeholder.
      const name = e.target.files?.[0]?.name;
      if (name) console.log('File selected:', name);
    },
    [],
  );

  return (
    <div className="border-t bg-background p-3">
      <div className="mx-auto flex max-w-3xl items-end gap-2">
        {/* File attachment button */}
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 shrink-0"
          onClick={() => fileInputRef.current?.click()}
          title={t('chat.input.attachFile')}
        >
          <Paperclip className="h-4 w-4" />
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={handleFileSelect}
        />

        {/* Text input */}
        <Textarea
          ref={textareaRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('chat.input.placeholder')}
          rows={1}
          className="min-h-[40px] resize-none"
          disabled={isLoading}
        />

        {/* Web search toggle */}
        <Button
          variant={webSearchEnabled ? 'default' : 'ghost'}
          size="icon"
          className="h-9 w-9 shrink-0"
          onClick={toggleWebSearch}
          title={
            webSearchEnabled
              ? t('chat.input.webSearchOn')
              : t('chat.input.webSearchOff')
          }
        >
          <Globe
            className={`h-4 w-4 ${
              webSearchEnabled ? '' : 'text-muted-foreground'
            }`}
          />
        </Button>

        {/* Send / Stop button */}
        {isStreaming ? (
          <Button
            variant="destructive"
            size="icon"
            className="h-9 w-9 shrink-0"
            onClick={stopStream}
          >
            <span className="text-sm">■</span>
          </Button>
        ) : (
          <Button
            onClick={handleSend}
            disabled={!inputValue.trim() || isLoading}
            className="h-9 shrink-0"
          >
            {t('chat.input.send')}
          </Button>
        )}
      </div>
    </div>
  );
}
