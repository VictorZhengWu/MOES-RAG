/**
 * Register form with client-side validation.
 *
 * WHY: Same pattern as LoginForm — validates inputs and stores user
 * in the auth store. Phase 2 will POST to a real registration endpoint.
 */

'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import Link from 'next/link';

export function RegisterForm() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!username.trim()) {
      setError('Username is required.');
      return;
    }
    if (!email.includes('@')) {
      setError(t('auth.errors.invalidEmail'));
      return;
    }
    if (password.length < 8) {
      setError(t('auth.errors.passwordLength'));
      return;
    }
    if (password !== confirmPassword) {
      setError(t('auth.errors.passwordsMatch'));
      return;
    }

    // Phase 1 mock registration
    login(
      {
        user_id: 'user_mock_02',
        username,
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
          <h1 className="text-2xl font-bold">
            {t('auth.register.title')}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t('auth.register.subtitle')}
          </p>
        </div>

        {error && (
          <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">
            {error}
          </p>
        )}

        <div className="space-y-3">
          <Input
            placeholder={t('auth.register.username')}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoFocus
          />
          <Input
            type="email"
            placeholder={t('auth.register.email')}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Input
            type="password"
            placeholder={t('auth.register.password')}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Input
            type="password"
            placeholder={t('auth.register.confirmPassword')}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
          />
        </div>

        <Button type="submit" className="w-full">
          {t('auth.register.submit')}
        </Button>

        <p className="text-center text-sm text-muted-foreground">
          {t('auth.register.hasAccount')}{' '}
          <Link
            href={`/${locale}/login`}
            className="text-primary underline underline-offset-2"
          >
            {t('auth.register.login')}
          </Link>
        </p>
      </form>
    </div>
  );
}
