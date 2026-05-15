/**
 * Register form with client-side validation, social sign-up buttons,
 * and a back button to return to chat without registering.
 */

'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { SocialButtons } from './social-buttons';
import { ArrowLeft } from 'lucide-react';
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

    if (!username.trim()) { setError('Username is required.'); return; }
    if (!email.includes('@')) { setError(t('auth.errors.invalidEmail')); return; }
    if (password.length < 8) { setError(t('auth.errors.passwordLength')); return; }
    if (password !== confirmPassword) { setError(t('auth.errors.passwordsMatch')); return; }

    login(
      { user_id: 'user_mock_02', username, email, role: 'viewer' },
      'mock-token',
    );
    router.push(`/${locale}/chat`);
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">
        {/* Back button */}
        <Link
          href={`/${locale}/chat`}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('common.back')}
        </Link>

        <div>
          <h1 className="text-2xl font-bold">{t('auth.register.title')}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t('auth.register.subtitle')}</p>
        </div>

        {error && (
          <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</p>
        )}

        {/* Email/password registration — primary method on top */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <Input placeholder={t('auth.register.username')} value={username}
            onChange={(e) => setUsername(e.target.value)} required autoFocus />
          <Input type="email" placeholder={t('auth.register.email')} value={email}
            onChange={(e) => setEmail(e.target.value)} required />
          <Input type="password" placeholder={t('auth.register.password')} value={password}
            onChange={(e) => setPassword(e.target.value)} required />
          <Input type="password" placeholder={t('auth.register.confirmPassword')} value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)} required />
          <Button type="submit" className="w-full">{t('auth.register.submit')}</Button>
        </form>

        {/* Social sign-up — secondary, below the main form */}
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <Separator />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-background px-2 text-muted-foreground">or continue with</span>
          </div>
        </div>

        <SocialButtons />

        <p className="text-center text-sm text-muted-foreground">
          {t('auth.register.hasAccount')}{' '}
          <Link href={`/${locale}/login`} className="text-primary underline underline-offset-2">
            {t('auth.register.login')}
          </Link>
        </p>
      </div>
    </div>
  );
}
