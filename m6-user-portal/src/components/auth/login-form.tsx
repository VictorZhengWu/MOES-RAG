/**
 * Login form with email/password validation.
 *
 * WHY: Phase 1 connects to Mock Server (no real auth), but the form
 * validates input format client-side and updates the auth store on
 * "login" so the sidebar and other components react correctly.
 * In Phase 2, this form will POST to a real /auth/login endpoint.
 */

'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Link from 'next/link';

export function LoginForm() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.includes('@')) {
      setError(t('auth.errors.invalidEmail'));
      return;
    }
    if (password.length < 8) {
      setError(t('auth.errors.passwordLength'));
      return;
    }

    // Phase 1 mock login — stores user in Zustand + localStorage
    login(
      {
        user_id: 'user_mock_01',
        username: email.split('@')[0],
        email,
        role: 'viewer',
      },
      'mock-token',
    );
    router.push(`/${locale}/chat`);
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-5"
      >
        <div>
          <h1 className="text-2xl font-bold">{t('auth.login.title')}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t('auth.login.subtitle')}
          </p>
        </div>

        {error && (
          <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <div className="space-y-3">
          <Input
            type="email"
            placeholder={t('auth.login.email')}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
          />
          <Input
            type="password"
            placeholder={t('auth.login.password')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <Button type="submit" className="w-full">
          {t('auth.login.submit')}
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          {t('auth.login.noAccount')}{' '}
          <Link
            href={`/${locale}/register`}
            className="text-primary underline underline-offset-2"
          >
            {t('auth.login.register')}
          </Link>
        </p>
      </form>
    </div>
  );
}
