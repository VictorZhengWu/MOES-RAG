/**
 * Global drag-and-drop overlay — appears when files are dragged
 * anywhere over the browser window. Shows a prompt message and
 * handles the actual file drop event.
 */

'use client';

import { useEffect, useState, useCallback } from 'react';
import { useTranslations } from 'next-intl';
import { Paperclip } from 'lucide-react';
import type { FileAttachment } from '@/types';

export function useGlobalDrop(onFilesDropped: (files: FileAttachment[]) => void) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [dragCounter, setDragCounter] = useState(0);

  const handleDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragCounter((c) => c + 1);
    if (e.dataTransfer?.types.includes('Files')) {
      setIsDragOver(true);
    }
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragCounter((c) => {
      const next = c - 1;
      if (next <= 0) setIsDragOver(false);
      return Math.max(0, next);
    });
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
    setDragCounter(0);

    const files = e.dataTransfer?.files;
    if (!files || files.length === 0) return;

    const dropped: FileAttachment[] = [];
    for (let i = 0; i < files.length; i++) {
      dropped.push({ name: files[i].name, size: files[i].size, file: files[i] });
    }
    onFilesDropped(dropped);
  }, [onFilesDropped]);

  useEffect(() => {
    window.addEventListener('dragenter', handleDragEnter);
    window.addEventListener('dragleave', handleDragLeave);
    window.addEventListener('dragover', handleDragOver);
    window.addEventListener('drop', handleDrop);
    return () => {
      window.removeEventListener('dragenter', handleDragEnter);
      window.removeEventListener('dragleave', handleDragLeave);
      window.removeEventListener('dragover', handleDragOver);
      window.removeEventListener('drop', handleDrop);
    };
  }, [handleDragEnter, handleDragLeave, handleDragOver, handleDrop]);

  return isDragOver;
}

export function DropOverlay({ visible }: { visible: boolean }) {
  const t = useTranslations();

  if (!visible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/70 backdrop-blur-sm pointer-events-none">
      <div className="flex flex-col items-center gap-4 rounded-2xl border-2 border-dashed border-primary/50 bg-background/90 p-12 shadow-2xl">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
          <Paperclip className="h-8 w-8 text-primary" />
        </div>
        <div className="text-center">
          <p className="text-lg font-semibold">Add anything</p>
          <p className="text-sm text-muted-foreground">
            Drop any file here to add it to the conversation
          </p>
        </div>
      </div>
    </div>
  );
}
