/** Minimal admin global state. Most pages manage their own data via API calls. */

import { create } from 'zustand';
import type { SupportedLanguage } from '@/types';

interface AdminState {
  language: SupportedLanguage;
  sidebarCollapsed: boolean;
  setLanguage: (lang: SupportedLanguage) => void;
  toggleSidebar: () => void;
}

export const useAdminStore = create<AdminState>((set) => ({
  language: 'en',
  sidebarCollapsed: false,
  setLanguage: (lang) => set({ language: lang }),
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
}));
