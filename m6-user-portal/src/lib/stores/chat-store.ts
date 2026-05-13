/**
 * Chat state store (Zustand).
 *
 * Manages the current conversation: messages, streaming state, input value,
 * web search toggle, and citation panel selection.
 *
 * WHY: Zustand over Redux/Context — zero boilerplate, no Provider wrapper,
 * works both inside and outside React components. For a chat app where
 * state updates every stream token, Zustand's selector-based re-render
 * control prevents unnecessary re-renders in unaffected components.
 */

import { create } from 'zustand';
import type { Message, Citation } from '@/types';

interface ChatState {
  messages: Message[];
  citations: Citation[];
  isLoading: boolean;
  isStreaming: boolean;
  inputValue: string;
  webSearchEnabled: boolean;
  selectedCitationIndex: number | null;

  setInputValue: (value: string) => void;
  addMessage: (msg: Message) => void;
  appendToLastMessage: (content: string) => void;
  setCitations: (citations: Citation[]) => void;
  setSelectedCitationIndex: (index: number | null) => void;
  setLoading: (loading: boolean) => void;
  setStreaming: (streaming: boolean) => void;
  toggleWebSearch: () => void;
  clearMessages: () => void;
  loadMessages: (messages: Message[]) => void;
}

export const useChatStore = create<ChatState>((set) => ({
  messages: [],
  citations: [],
  isLoading: false,
  isStreaming: false,
  inputValue: '',
  webSearchEnabled: false,
  selectedCitationIndex: null,

  setInputValue: (value) => set({ inputValue: value }),

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages, msg] })),

  appendToLastMessage: (content) =>
    set((s) => {
      const msgs = [...s.messages];
      const last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        msgs[msgs.length - 1] = { ...last, content: last.content + content };
      } else {
        msgs.push({ role: 'assistant', content });
      }
      return { messages: msgs };
    }),

  setCitations: (citations) => set({ citations }),
  setSelectedCitationIndex: (index) => set({ selectedCitationIndex: index }),
  setLoading: (loading) => set({ isLoading: loading }),
  setStreaming: (streaming) => set({ isStreaming: streaming }),
  toggleWebSearch: () => set((s) => ({ webSearchEnabled: !s.webSearchEnabled })),
  clearMessages: () => set({ messages: [], citations: [], selectedCitationIndex: null }),
  loadMessages: (messages) => set({ messages }),
}));
