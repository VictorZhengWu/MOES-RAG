/**
 * Conversation list store.
 *
 * WHY: The sidebar needs to react to conversation list changes
 * (new conversation created, renamed, deleted). A dedicated store
 * prevents prop-drilling from the chat page through layout to sidebar.
 * The token from auth-store is passed to API calls for authenticated
 * conversation access.
 */

import { create } from 'zustand';
import type { ConversationSummary } from '@/types';
import * as convApi from '@/lib/api/conversations';
import { useAuthStore } from './auth-store';

interface ConversationState {
  conversations: ConversationSummary[];
  activeId: string | null;
  isLoading: boolean;

  setActiveId: (id: string | null) => void;
  fetchConversations: () => Promise<void>;
  removeConversation: (id: string) => Promise<void>;
  renameConversation: (id: string, title: string) => Promise<void>;
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  conversations: [],
  activeId: null,
  isLoading: false,

  setActiveId: (id) => set({ activeId: id }),

  fetchConversations: async () => {
    const token = useAuthStore.getState().token ?? undefined;
    set({ isLoading: true });
    try {
      const res = await convApi.listConversations(token);
      set({ conversations: res.conversations });
    } finally {
      set({ isLoading: false });
    }
  },

  removeConversation: async (id) => {
    const token = useAuthStore.getState().token ?? undefined;
    await convApi.deleteConversation(id, token);
    set((s) => ({
      conversations: s.conversations.filter(
        (c) => c.conversation_id !== id,
      ),
    }));
  },

  renameConversation: async (id, title) => {
    const token = useAuthStore.getState().token ?? undefined;
    await convApi.renameConversation(id, title, token);
    set((s) => ({
      conversations: s.conversations.map((c) =>
        c.conversation_id === id ? { ...c, title } : c,
      ),
    }));
  },
}));
