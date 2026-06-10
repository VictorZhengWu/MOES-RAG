/**
 * Reset password form — sets a new password using a reset token from email.
 *
 * WHAT: Takes the token from the URL query param, asks for a new password,
 *       and POSTs to M8 /auth/reset-password. On success, redirects to login.
 */
'use client';

import { useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { authResetPassword } from '@/lib/api/auth';
import { ArrowLeft, Loader2, ShieldCheck } from 'lucide-react';
import Link from 'next/link';

export function ResetPasswordForm() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token') || '';

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!token) {
      setError(t('auth.errors.resetTokenInvalid'));
      return;
    }
    if (password.length < 8) {
      setError(t('auth.errors.passwordLength'));
      return;
    }
    if (password !== confirm) {
      setError(t('auth.errors.passwordsMatch'));
      return;
    }

    setSubmitting(true);
    try {
      await authResetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reset password');
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-sm text-center space-y-4">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
            <ShieldCheck className="h-6 w-6 text-green-600 dark:text-green-400" />
          </div>
          <h1 className="text-xl font-bold">{t('auth.resetPassword.done.title')}</h1>
          <p className="text-sm text-muted-foreground">
            {t('auth.resetPassword.done.message')}
          </p>
          <Link href={`/${locale}/login`}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90">
            Sign in
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">
        <Link href={`/${locale}/login`}
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />
          {t('common.back')}
        </Link>

        <div>
          <h1 className="text-2xl font-bold">{t('auth.resetPassword.title')}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t('auth.resetPassword.subtitle')}
          </p>
        </div>

        {error && (
          <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</p>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <Input type="password" placeholder={t('auth.resetPassword.newPassword')} value={password}
            onChange={(e) => setPassword(e.target.value)} required autoFocus minLength={8} />
          <Input type="password" placeholder={t('auth.resetPassword.confirmPassword')} value={confirm}
            onChange={(e) => setConfirm(e.target.value)} required minLength={8} />
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? <Loader2 className="h-4 w-4 animate-spin mx-auto" /> : t('auth.resetPassword.submit')}
          </Button>
        </form>
      </div>
    </div>
  );
}
