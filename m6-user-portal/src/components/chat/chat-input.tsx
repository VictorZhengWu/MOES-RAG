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

import { useState, useRef, useCallback, DragEvent } from 'react';
import type { KeyboardEvent } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Paperclip, Globe, X } from 'lucide-react';
import { useChatStore } from '@/lib/stores/chat-store';
import { useChatStream } from '@/lib/hooks/use-chat-stream';

interface AttachedFile {
  name: string;
  size: number;
}

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
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);

  const addFiles = useCallback((files: FileList | null) => {
    if (!files) return;
    const newFiles: AttachedFile[] = [];
    for (let i = 0; i < files.length; i++) {
      newFiles.push({ name: files[i].name, size: files[i].size });
    }
    setAttachedFiles((prev) => [...prev, ...newFiles]);
    // Phase 2: actual file upload to server
  }, []);

  const removeFile = useCallback((index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleSend = async () => {
    const content = inputValue.trim();
    if (!content || isLoading) return;
    setInputValue('');
    setAttachedFiles([]);

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
      addFiles(e.target.files);
      // Reset so the same file can be re-selected
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
    [addFiles],
  );

  // Drag-and-drop handlers
  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    addFiles(e.dataTransfer.files);
  };

  return (
    <div
      className={`border-t bg-background p-3 transition-colors ${
        isDragOver ? 'bg-primary/5 ring-2 ring-primary/20 rounded-lg' : ''
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Attached file chips */}
      {attachedFiles.length > 0 && (
        <div className="mx-auto mb-2 flex max-w-3xl flex-wrap gap-1.5">
          {attachedFiles.map((file, i) => (
            <Badge
              key={i}
              variant="secondary"
              className="gap-1 pr-1 text-xs cursor-default"
            >
              {file.name}
              <button
                onClick={() => removeFile(i)}
                className="ml-0.5 rounded-full hover:bg-muted-foreground/20 p-0.5"
                aria-label={`Remove ${file.name}`}
              >
                <X className="h-3 w-3" />
              </button>
            </Badge>
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
