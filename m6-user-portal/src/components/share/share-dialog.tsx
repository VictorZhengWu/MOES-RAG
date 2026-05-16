/**
 * Share dialog — placeholder that shows a fake shareable link.
 * Phase 2 will generate real share links via the backend.
 */

'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { X, Check, Copy } from 'lucide-react';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function ShareDialog({ open, onClose }: Props) {
  const t = useTranslations();
  const [copied, setCopied] = useState(false);

  // Mock share link
  const shareLink = 'https://mo-expert.com/share/conv_' + Math.random().toString(36).slice(2, 10);

  const handleCopy = () => {
    navigator.clipboard.writeText(shareLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={onClose}>
      <div
        className="w-[400px] rounded-xl border bg-background shadow-2xl p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{t('share.title')}</h2>
          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <p className="text-sm text-muted-foreground mb-4">{t('share.description')}</p>
        <div className="flex gap-2">
          <Input value={shareLink} readOnly className="flex-1 text-sm" />
          <Button size="sm" className="gap-1.5" onClick={handleCopy}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
            {copied ? t('share.copied') : t('share.copyLink')}
          </Button>
        </div>
      </div>
    </div>
  );
}
