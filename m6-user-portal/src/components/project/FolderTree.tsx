/**
 * FolderTree — tree view for project conversations (00107-01/06).
 *
 * WHAT: Hierarchical tree showing Phase → Discipline → Conversations.
 *       Supports expand/collapse, drag-drop conversations to folders,
 *       and right-click context menu for folder management.
 */
'use client';

import { useState, useCallback } from 'react';
import { ChevronRight, ChevronDown, Folder, FileText, Plus, Trash2 } from 'lucide-react';

interface Conversation {
  conversation_id: string;
  folder_path: string;
  tags: string[];
}

interface TreeNode {
  name: string;
  path: string;
  children: TreeNode[];
  conversations: Conversation[];
  count: number;
}

function buildTree(conversations: Conversation[]): TreeNode {
  const root: TreeNode = { name: 'Project', path: '', children: [], conversations: [], count: 0 };
  const nodeMap: Record<string, TreeNode> = { '': root };

  for (const conv of conversations) {
    const parts = (conv.folder_path || 'Uncategorized').split('/').filter(Boolean);
    if (parts.length === 0) parts.push('Uncategorized');

    let currentPath = '';
    for (let i = 0; i < parts.length; i++) {
      const parentPath = currentPath;
      currentPath = currentPath ? `${currentPath}/${parts[i]}` : parts[i];

      if (!nodeMap[currentPath]) {
        const node: TreeNode = {
          name: parts[i],
          path: currentPath,
          children: [],
          conversations: [],
          count: 0,
        };
        nodeMap[currentPath] = node;
        nodeMap[parentPath].children.push(node);
      }
    }
    // Add conversation to the deepest node
    nodeMap[currentPath].conversations.push(conv);
  }

  // Calculate counts
  function calcCount(node: TreeNode): number {
    node.count = node.conversations.length;
    for (const child of node.children) {
      node.count += calcCount(child);
    }
    return node.count;
  }
  calcCount(root);
  return root;
}

export function FolderTree({
  conversations,
  onSelect,
  onLinkConversation,
  onDeleteFolder,
  onCreateFolder,
}: {
  conversations: Conversation[];
  onSelect: (convId: string) => void;
  onLinkConversation?: (convId: string, folderPath: string) => void;
  onDeleteFolder?: (folderPath: string) => void;
  onCreateFolder?: (parentPath: string, name: string) => void;
}) {
  const tree = buildTree(conversations);
  const [expanded, setExpanded] = useState<Set<string>>(new Set(tree.children.map(c => c.path)));
  const [dragOverPath, setDragOverPath] = useState<string | null>(null);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; path: string } | null>(null);
  const [newFolderInput, setNewFolderInput] = useState<{ parentPath: string } | null>(null);
  const [newFolderName, setNewFolderName] = useState('');

  const toggleExpand = (path: string) => {
    setExpanded(prev => {
      const next = new Set(prev);
      next.has(path) ? next.delete(path) : next.add(path);
      return next;
    });
  };

  const handleDragStart = (e: React.DragEvent, convId: string) => {
    e.dataTransfer.setData('text/plain', convId);
    e.dataTransfer.effectAllowed = 'move';
  };

  const handleDragOver = (e: React.DragEvent, path: string) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    setDragOverPath(path);
  };

  const handleDrop = (e: React.DragEvent, folderPath: string) => {
    e.preventDefault();
    setDragOverPath(null);
    const convId = e.dataTransfer.getData('text/plain');
    if (convId && onLinkConversation) {
      onLinkConversation(convId, folderPath);
    }
  };

  const handleContextMenu = (e: React.MouseEvent, path: string) => {
    e.preventDefault();
    setContextMenu({ x: e.clientX, y: e.clientY, path });
  };

  const renderNode = (node: TreeNode, depth: number) => {
    const isExpanded = expanded.has(node.path);
    const isDragOver = dragOverPath === node.path;
    const hasChildren = node.children.length > 0;

    return (
      <div key={node.path || 'root'}>
        {node.path && (
          <div
            className={`flex items-center gap-1 px-2 py-1 text-sm rounded cursor-pointer
              ${isDragOver ? 'bg-primary/10 border border-primary/30' : 'hover:bg-muted/50'}`}
            style={{ paddingLeft: `${depth * 16 + 8}px` }}
            onClick={() => hasChildren && toggleExpand(node.path)}
            onDragOver={(e) => handleDragOver(e, node.path)}
            onDrop={(e) => handleDrop(e, node.path)}
            onContextMenu={(e) => handleContextMenu(e, node.path)}
          >
            {hasChildren ? (
              isExpanded ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            ) : <span className="w-3.5" />}
            <Folder className="h-3.5 w-3.5 shrink-0 text-blue-500" />
            <span className="flex-1 truncate text-xs font-medium">{node.name}</span>
            {node.count > 0 && (
              <span className="text-[10px] text-muted-foreground bg-muted px-1.5 py-0.5 rounded-full">{node.count}</span>
            )}
          </div>
        )}
        {(!node.path || isExpanded) && (
          <>
            {node.children.map(child => renderNode(child, depth + 1))}
            {node.conversations.map(conv => (
              <div
                key={conv.conversation_id}
                className="flex items-center gap-1 px-2 py-1 text-sm rounded cursor-pointer hover:bg-muted/50"
                style={{ paddingLeft: `${(depth + 1) * 16 + 8}px` }}
                onClick={() => onSelect(conv.conversation_id)}
                draggable
                onDragStart={(e) => handleDragStart(e, conv.conversation_id)}
              >
                <FileText className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="flex-1 truncate text-xs">{conv.conversation_id.slice(0, 12)}</span>
              </div>
            ))}
          </>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-0.5">
      {tree.children.map(child => renderNode(child, 0))}
      {tree.children.length === 0 && (
        <p className="text-xs text-muted-foreground text-center py-4">No conversations yet</p>
      )}

      {/* Inline new-folder dialog */}
      {newFolderInput && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/20" onClick={() => setNewFolderInput(null)}>
          <div className="bg-background border rounded-lg shadow-lg p-4 w-72" onClick={e => e.stopPropagation()}>
            <p className="text-sm font-medium mb-2">New folder in: {newFolderInput.parentPath || 'root'}</p>
            <input type="text" value={newFolderName} onChange={e => setNewFolderName(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && newFolderName.trim() && onCreateFolder) {
                  onCreateFolder(newFolderInput.parentPath, newFolderName.trim());
                  setNewFolderInput(null); setNewFolderName('');
                }
                if (e.key === 'Escape') { setNewFolderInput(null); setNewFolderName(''); }
              }}
              placeholder="Folder name" className="w-full rounded-lg border px-3 py-2 text-sm mb-2" autoFocus />
            <div className="flex gap-2 justify-end">
              <button className="px-3 py-1 text-xs rounded bg-primary text-primary-foreground"
                onClick={() => {
                  if (newFolderName.trim() && onCreateFolder) {
                    onCreateFolder(newFolderInput.parentPath, newFolderName.trim());
                  }
                  setNewFolderInput(null); setNewFolderName('');
                }}>Create</button>
              <button className="px-3 py-1 text-xs rounded border"
                onClick={() => { setNewFolderInput(null); setNewFolderName(''); }}>Cancel</button>
            </div>
          </div>
        </div>
      )}

      {/* Context menu */}
      {contextMenu && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setContextMenu(null)} />
          <div className="fixed z-50 bg-background border rounded-lg shadow-lg py-1 text-xs"
            style={{ left: contextMenu.x, top: contextMenu.y }}>
            <button className="flex items-center gap-1.5 px-3 py-1.5 hover:bg-muted w-full text-left"
              onClick={() => {
                const path = contextMenu.path;
                setContextMenu(null);
                setNewFolderInput({ parentPath: path });
                setNewFolderName('');
              }}>
              <Plus className="h-3 w-3" /> New Sub-folder
            </button>
            <button className="flex items-center gap-1.5 px-3 py-1.5 hover:bg-muted w-full text-left text-destructive"
              onClick={() => {
                const path = contextMenu.path;
                setContextMenu(null);
                const isEmpty = !conversations.some(c => c.folder_path === path || c.folder_path?.startsWith(path + '/'));
                if (isEmpty && onDeleteFolder) {
                  onDeleteFolder(path);
                }
              }}>
              <Trash2 className="h-3 w-3" /> Delete (if empty)
            </button>
          </div>
        </>
      )}
    </div>
  );
}
