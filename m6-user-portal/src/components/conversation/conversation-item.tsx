/**
 * A single conversation entry with hover "..." context menu.
 *
 * Menu items: Share, Rename, Move to project (submenu), Pin, Delete.
 * Icons on each item. "Move to project" shows recent 10 projects.
 */

'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import type { ConversationSummary } from '@/types';
import { useConversationStore } from '@/lib/stores/conversation-store';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubTrigger,
  DropdownMenuSubContent,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Share2,
  Pencil,
  FolderInput,
  Pin,
  Trash2,
  MoreHorizontal,
} from 'lucide-react';

// Mock projects for the submenu
const MOCK_PROJECTS = [
  'LNG Carrier Design',
  'Ballast Water Compliance',
  'Bulk Carrier Hatch Study',
  'Offshore Wind Platform',
  'Drillship DP Analysis',
  'Container Ship Fatigue',
  'Tanker Structural Rules',
  'FPSO Mooring Systems',
  'Subsea Pipeline Standards',
  'Arctic Vessel Notation',
];

interface Props {
  conversation: ConversationSummary;
  isActive: boolean;
  onSelect: () => void;
}

export function ConversationItem({ conversation, isActive, onSelect }: Props) {
  const t = useTranslations();
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(conversation.title);
  const [menuOpen, setMenuOpen] = useState(false);
  const { renameConversation, removeConversation } = useConversationStore();

  const handleDoubleClick = () => {
    setIsEditing(true);
    setEditTitle(conversation.title);
  };

  const handleRename = () => {
    if (editTitle.trim()) renameConversation(conversation.conversation_id, editTitle.trim());
    setIsEditing(false);
  };

  const handleShare = () => {
    // Phase 2: actual share logic
    alert(`Share link: https://mo-expert.com/share/${conversation.conversation_id}`);
  };

  const handleMoveToProject = (project: string) => {
    console.log(`Move ${conversation.conversation_id} → ${project}`);
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

      {/* "..." menu — visible on hover.
          Use <div> inside DropdownMenuTrigger to avoid nested <button> error (Base UI). */}
      <DropdownMenu open={menuOpen} onOpenChange={setMenuOpen}>
        <DropdownMenuTrigger
          className={cn(
            'h-6 w-6 flex items-center justify-center rounded-md hover:bg-muted transition-opacity',
            menuOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100',
          )}
          onClick={(e) => { e.stopPropagation(); setMenuOpen(true); }}
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48" onClick={(e) => e.stopPropagation()}>
          <DropdownMenuItem onClick={handleShare}>
            <Share2 className="mr-2 h-4 w-4" />
            {t('conversation.menu.share')}
          </DropdownMenuItem>
          <DropdownMenuItem onClick={handleDoubleClick}>
            <Pencil className="mr-2 h-4 w-4" />
            {t('conversation.menu.rename')}
          </DropdownMenuItem>
          <DropdownMenuSub>
            <DropdownMenuSubTrigger>
              <FolderInput className="mr-2 h-4 w-4" />
              {t('conversation.menu.moveToProject')}
            </DropdownMenuSubTrigger>
            <DropdownMenuSubContent className="w-52">
              <div className="px-2 py-1.5 text-xs text-muted-foreground font-medium">
                {t('conversation.menu.recentProjects')}
              </div>
              <DropdownMenuSeparator />
              {MOCK_PROJECTS.map((p) => (
                <DropdownMenuItem key={p} onClick={() => handleMoveToProject(p)}>
                  {p}
                </DropdownMenuItem>
              ))}
            </DropdownMenuSubContent>
          </DropdownMenuSub>
          <DropdownMenuItem onClick={() => console.log('Pin:', conversation.conversation_id)}>
            <Pin className="mr-2 h-4 w-4" />
            {t('conversation.menu.pin')}
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="text-destructive"
            onClick={() => removeConversation(conversation.conversation_id)}
          >
            <Trash2 className="mr-2 h-4 w-4" />
            {t('conversation.menu.delete')}
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
