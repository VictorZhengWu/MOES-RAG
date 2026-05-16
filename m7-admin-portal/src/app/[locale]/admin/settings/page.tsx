/**
 * Admin Settings page: language selector + theme toggle.
 */

'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { SUPPORTED_LANGUAGES, type SupportedLanguage } from '@/types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Sun, Moon, Monitor } from 'lucide-react';
import { useState } from 'react';

type Theme = 'light' | 'dark' | 'system';

function applyTheme(t: Theme) {
  const root = document.documentElement;
  if (t === 'dark') root.classList.add('dark');
  else if (t === 'light') root.classList.remove('dark');
  else root.classList.toggle('dark', window.matchMedia('(prefers-color-scheme: dark)').matches);
}

export default function AdminSettingsPage() {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [theme, setTheme] = useState<Theme>('system');

  useEffect(() => { applyTheme(theme); }, [theme]);

  useEffect(() => {
    if (theme !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const h = () => applyTheme('system');
    mq.addEventListener('change', h);
    return () => mq.removeEventListener('change', h);
  }, [theme]);

  const switchLang = (lang: SupportedLanguage) => {
    const segments = pathname.split('/').filter(Boolean);
    if (['en', 'zh', 'ko', 'ja', 'no'].includes(segments[0])) segments[0] = lang;
    else segments.unshift(lang);
    router.push('/' + segments.join('/'));
  };

  return (
    <div className="mx-auto max-w-2xl p-8">
      <h1 className="text-xl font-bold">{t('nav.settings')}</h1>
      <p className="text-sm text-muted-foreground mt-1 mb-8">Configure admin preferences.</p>

      <div className="space-y-8">
        {/* Language */}
        <Card>
          <CardHeader><CardTitle className="text-base">{t('admin.settings.language.label')}</CardTitle></CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">{t('admin.settings.language.description')}</p>
            <select
              value={locale}
              onChange={(e) => switchLang(e.target.value as SupportedLanguage)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
            >
              {SUPPORTED_LANGUAGES.map((lang) => (
                <option key={lang.code} value={lang.code}>{lang.label}</option>
              ))}
            </select>
          </CardContent>
        </Card>

        {/* Theme */}
        <Card>
          <CardHeader><CardTitle className="text-base">{t('admin.settings.theme.label')}</CardTitle></CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-2">
              {([
                { key: 'light' as Theme, icon: Sun, label: t('admin.settings.theme.light') },
                { key: 'dark' as Theme, icon: Moon, label: t('admin.settings.theme.dark') },
                { key: 'system' as Theme, icon: Monitor, label: t('admin.settings.theme.system') },
              ]).map(({ key, icon: Icon, label }) => (
                <button
                  key={key}
                  onClick={() => setTheme(key)}
                  className={`flex flex-col items-center gap-1.5 rounded-lg border p-3 text-xs transition-colors ${
                    theme === key
                      ? 'border-primary bg-primary/5 text-primary'
                      : 'border-border hover:bg-muted'
                  }`}
                >
                  <Icon className="h-5 w-5" />
                  {label}
                </button>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
