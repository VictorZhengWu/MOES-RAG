/**
 * Authentication state store.
 *
 * WHY: Multiple components (sidebar footer, header, chat, conversation
 * sidebar) need to react to login/logout. A centralized store avoids
 * prop drilling. Guest mode: authStatus='guest', user=null.
 * Authenticated: authStatus='authenticated', user populated.
 *
 * Persisted to localStorage via zustand/middleware persist so the
 * user stays logged in across page reloads.
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { UserProfile, AuthStatus } from '@/types';

interface AuthState {
  authStatus: AuthStatus;
  user: UserProfile | null;
  token: string | null;

  login: (user: UserProfile, token: string) => void;
  logout: () => void;
  setGuest: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      authStatus: 'loading' as AuthStatus,
      user: null,
      token: null,

      login: (user, token) =>
        set({ authStatus: 'authenticated', user, token }),

      logout: () =>
        set({ authStatus: 'guest', user: null, token: null }),

      setGuest: () =>
        set({ authStatus: 'guest', user: null, token: null }),
    }),
    {
      name: 'm6-auth',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        authStatus: state.authStatus,
      }),
    },
  ),
);
