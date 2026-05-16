/**
 * Chat input bar: textarea + file attachment + web search toggle + send/stop.
 *
 * Supports both click-to-upload and drag-and-drop file attachment.
 * Selected files appear as removable chips above the input area.
 *
 * Layout:
 * ┌─────────────────────────────────────────────────────────┐
 * │ [chip: file.pdf ×]                                     │
 * │ [📎] [_____________________________] [🌐] [Send/■]    │
 * └─────────────────────────────────────────────────────────┘
 */

'use client';

import { useRef, useCallback } from 'react';
import type { KeyboardEvent } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Paperclip, Globe, X, FileText } from 'lucide-react';
import type { FileAttachment } from '@/types';
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
    attachedFiles,
    addFiles,
    removeFile,
    clearFiles,
  } = useChatStore();
  const { startStream, stopStream } = useChatStream();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleAddFiles = useCallback((files: FileList | null) => {
    if (!files) return;
    const newFiles: FileAttachment[] = [];
    for (let i = 0; i < files.length; i++) {
      const f = files[i];
      newFiles.push({ name: f.name, size: f.size, file: f });
    }
    addFiles(newFiles);
  }, [addFiles]);

  const handleSend = async () => {
    const content = inputValue.trim();
    if (!content || isLoading) return;
    setInputValue('');

    const files = [...attachedFiles];
    clearFiles();

    await startStream({
      model: 'marine-rag-mock',
      messages: [...messages, {
        role: 'user',
        content,
        attachments: files.length > 0 ? files : undefined,
      }],
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
      handleAddFiles(e.target.files);
      // Reset so the same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
    [handleAddFiles],
  );

  return (
    <div className="border-t bg-background p-3">
      {/* Attached file chips with icons */}
      {attachedFiles.length > 0 && (
        <div className="mx-auto mb-2 flex max-w-3xl flex-wrap gap-2">
          {attachedFiles.map((file, i) => (
            <div
              key={i}
              className="flex items-center gap-2 rounded-lg border bg-muted/30 px-3 py-2 text-sm"
            >
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="max-w-[200px] truncate">{file.name}</span>
              <button
                onClick={() => removeFile(i)}
                className="ml-1 rounded-full p-0.5 hover:bg-muted-foreground/20"
                aria-label={`Remove ${file.name}`}
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

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
          multiple
          onChange={handleFileSelect}
        />

        {/* Text input — 3 rows for comfortable multi-line editing */}
        <Textarea
          ref={textareaRef}
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('chat.input.placeholder')}
          rows={3}
          className="min-h-[60px] resize-none"
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
