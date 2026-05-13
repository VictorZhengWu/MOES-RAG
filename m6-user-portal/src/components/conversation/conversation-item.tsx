/**
 * A single conversation entry in the sidebar.
 * Supports click-to-open, inline rename (double-click), and delete.
 */

'use client';

import { useState } from 'react';
import type { ConversationSummary } from '@/types';
import { useConversationStore } from '@/lib/stores/conversation-store';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Trash2Icon } from 'lucide-react';

interface Props {
  conversation: ConversationSummary;
  isActive: boolean;
  onSelect: () => void;
}

export function ConversationItem({
  conversation,
  isActive,
  onSelect,
}: Props) {
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(conversation.title);
  const { renameConversation, removeConversation } = useConversationStore();

  const handleDoubleClick = () => {
    setIsEditing(true);
    setEditTitle(conversation.title);
  };

  const handleRename = () => {
    if (editTitle.trim()) {
      renameConversation(conversation.conversation_id, editTitle.trim());
    }
    setIsEditing(false);
  };

  return (
    <div
      className={cn(
        'group flex items-center gap-2 rounded-lg px-3 py-2 text-sm cursor-pointer',
        isActive ? 'bg-accent' : 'hover:bg-accent/50',
      )}
      onClick={onSelect}
      onDoubleClick={handleDoubleClick}
    >
      {isEditing ? (
        <Input
          value={editTitle}
          onChange={(e) => setEditTitle(e.target.value)}
          onBlur={handleRename}
          onKeyDown={(e) => e.key === 'Enter' && handleRename()}
          autoFocus
          className="h-7 text-xs"
          onClick={(e) => e.stopPropagation()}
        />
      ) : (
        <span className="flex-1 truncate">{conversation.title}</span>
      )}
      <Button
        variant="ghost"
        size="icon"
        className="h-6 w-6 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={(e) => {
          e.stopPropagation();
          removeConversation(conversation.conversation_id);
        }}
      >
        <Trash2Icon className="h-3 w-3" />
      </Button>
    </div>
  );
}
