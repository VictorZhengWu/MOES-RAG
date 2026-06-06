/**
 * Login form with email/password validation, social login buttons,
 * and a back button to return to chat without logging in.
 */

'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { useAuthStore } from '@/lib/stores/auth-store';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Separator } from '@/components/ui/separator';
import { SocialButtons } from './social-buttons';
import { authLogin } from '@/lib/api/auth';
import { ArrowLeft, Loader2 } from 'lucide-react';
import Link from 'next/link';

export function LoginForm() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get('redirect') || `/${locale}/chat`;
  const login = useAuthStore((s) => s.login);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!email.includes('@')) {
      setError(t('auth.errors.invalidEmail'));
      return;
    }
    if (password.length < 6) {
      setError(t('auth.errors.passwordLength'));
      return;
    }

    setSubmitting(true);
    try {
      const result = await authLogin(email, password);
      login(result.user, result.token);
      router.push(redirectTo);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setSubmitting(false);
    }
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
          <h1 className="text-2xl font-bold">{t('auth.login.title')}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{t('auth.login.subtitle')}</p>
        </div>

        {error && (
          <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</p>
        )}

        {/* Email/password form — primary login method on top */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <Input type="email" placeholder={t('auth.login.email')} value={email}
            onChange={(e) => setEmail(e.target.value)} required autoFocus />
          <Input type="password" placeholder={t('auth.login.password')} value={password}
            onChange={(e) => setPassword(e.target.value)} required />
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? <Loader2 className="h-4 w-4 animate-spin mx-auto" /> : t('auth.login.submit')}
          </Button>
        </form>

        {/* Social login — secondary, below the main form */}
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
          {t('auth.login.noAccount')}{' '}
          <Link href={`/${locale}/register`} className="text-primary underline underline-offset-2">
            {t('auth.login.register')}
          </Link>
        </p>
      </div>
    </div>
  );
}
