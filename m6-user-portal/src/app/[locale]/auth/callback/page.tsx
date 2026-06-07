/**
 * OAuth Callback Page — handles redirect from M8 after OAuth login.
 *
 * WHAT: M8 redirects here after successful OAuth with token/user info in
 *       query params. This page stores the API key via useAuthStore.login()
 *       and redirects to the chat page.
 *
 * WHY: The OAuth flow goes: M6 → M8 → Provider → M8 → M6/callback → Chat.
 *      This page is the final landing point where the API key enters the
 *      frontend's localStorage.
 */

'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Loader2 } from 'lucide-react';

export default function OAuthCallbackPage() {
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const login = useAuthStore((s) => s.login);
  const [error, setError] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');
    const userId = searchParams.get('user_id');
    const username = searchParams.get('username');
    const email = searchParams.get('email');

    // Check for error from OAuth flow
    const oauthError = searchParams.get('error');
    if (oauthError) {
      setError(oauthError);
      setTimeout(() => router.push(`/${locale}/login?error=${oauthError}`), 2000);
      return;
    }

    if (token && userId) {
      login(
        {
          user_id: userId,
          username: username || 'user',
          email: email || '',
          role: 'basic',
        },
        token,
      );
      router.push(`/${locale}/chat`);
    } else {
      setError('missing_params');
      setTimeout(() => router.push(`/${locale}/login`), 2000);
    }
  }, [searchParams, login, router, locale]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="text-center space-y-4">
        {error ? (
          <>
            <p className="text-red-500 font-medium">Login failed</p>
            <p className="text-sm text-muted-foreground">{error}</p>
          </>
        ) : (
          <>
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary" />
            <p className="text-sm text-muted-foreground">Signing you in...</p>
          </>
        )}
      </div>
    </div>
  );
}
