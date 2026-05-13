/**
 * User settings store.
 *
 * Persists language preference to localStorage immediately for
 * instant UI response. Theme preference also persisted.
 *
 * WHY: Two-layer persistence — localStorage is the rendering source
 * of truth (no network round-trip on language switch), while the
 * server-side preference overrides localStorage on next login to
 * sync across devices. See design spec Section 8.
 */

import { create } from 'zustand';
import type { SupportedLanguage } from '@/types';

interface SettingsState {
  language: SupportedLanguage;
  theme: 'light' | 'dark' | 'system';

  setLanguage: (lang: SupportedLanguage) => void;
  setTheme: (theme: 'light' | 'dark' | 'system') => void;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  language: 'en',
  theme: 'system',

  setLanguage: (lang) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('m6-language', lang);
    }
    set({ language: lang });
  },

  setTheme: (theme) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('m6-theme', theme);
    }
    set({ theme });
  },
}));
