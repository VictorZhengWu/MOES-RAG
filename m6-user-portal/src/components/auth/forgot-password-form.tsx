/**
 * Forgot password form — enters email to receive a reset link.
 *
 * WHAT: POSTs email to M8 /auth/forgot-password. On success shows a
 *       confirmation message regardless of whether the email was found
 *       (prevents user enumeration). On 429 rate limit, shows cooldown.
 */
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { authForgotPassword } from '@/lib/api/auth';
import { ArrowLeft, Loader2, Mail } from 'lucide-react';
import Link from 'next/link';

export function ForgotPasswordForm() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!email.includes('@')) {
      setError(t('auth.errors.invalidEmail'));
      return;
    }
    setSubmitting(true);
    try {
      await authForgotPassword(email);
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to send reset email');
    } finally {
      setSubmitting(false);
    }
  };

  if (sent) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-sm text-center space-y-4">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-green-100 dark:bg-green-900">
            <Mail className="h-6 w-6 text-green-600 dark:text-green-400" />
          </div>
          <h1 className="text-xl font-bold">{t('auth.forgotPassword.sent.title')}</h1>
          <p className="text-sm text-muted-foreground">
            {t('auth.forgotPassword.sent.message')}
          </p>
          <Link href={`/${locale}/login`}
            className="inline-block text-sm text-primary underline underline-offset-2">
            {t('common.back')} to login
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
          <h1 className="text-2xl font-bold">{t('auth.forgotPassword.title')}</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {t('auth.forgotPassword.subtitle')}
          </p>
        </div>

        {error && (
          <p className="text-sm text-destructive bg-destructive/10 rounded-lg px-3 py-2">{error}</p>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <Input type="email" placeholder={t('auth.forgotPassword.email')} value={email}
            onChange={(e) => setEmail(e.target.value)} required autoFocus />
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? <Loader2 className="h-4 w-4 animate-spin mx-auto" /> : t('auth.forgotPassword.submit')}
          </Button>
        </form>
      </div>
    </div>
  );
}
