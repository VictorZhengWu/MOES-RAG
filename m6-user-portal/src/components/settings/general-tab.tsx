/**
 * General settings tab: theme selector and interface language.
 *
 * WHY: Centralizes appearance settings. Theme toggles between
 * Light/Dark/System. Language selector replaces the now-removed
 * header language switcher — all locale changes happen here.
 */

'use client';

import { useTranslations, useLocale } from 'next-intl';
import { useRouter, usePathname } from 'next/navigation';
import { SUPPORTED_LANGUAGES, type SupportedLanguage } from '@/types';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Sun, Moon, Monitor } from 'lucide-react';

type Theme = 'light' | 'dark' | 'system';

interface Props {
  theme: Theme;
  onThemeChange: (theme: Theme) => void;
}

export function GeneralTab({ theme, onThemeChange }: Props) {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  const switchLang = (lang: SupportedLanguage) => {
    const segments = pathname.split('/').filter(Boolean);
    if (['en', 'zh', 'ko', 'ja', 'no'].includes(segments[0])) {
      segments[0] = lang;
    } else {
      segments.unshift(lang);
    }
    router.push('/' + segments.join('/'));
  };

  const themes: { key: Theme; icon: typeof Sun; label: string }[] = [
    { key: 'light', icon: Sun, label: t('settings.theme.light') },
    { key: 'dark', icon: Moon, label: t('settings.theme.dark') },
    { key: 'system', icon: Monitor, label: t('settings.theme.system') },
  ];

  return (
    <div className="space-y-6">
      {/* Theme selector */}
      <div>
        <h3 className="text-sm font-medium">{t('settings.theme.label')}</h3>
        <div className="mt-3 grid grid-cols-3 gap-2">
          {themes.map(({ key, icon: Icon, label }) => (
            <button
              key={key}
              onClick={() => onThemeChange(key)}
              className={
                'flex flex-col items-center gap-1.5 rounded-lg border p-3 text-xs transition-colors ' +
                (theme === key
                  ? 'border-primary bg-primary/5 text-primary'
                  : 'border-border hover:bg-muted')
              }
            >
              <Icon className="h-5 w-5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      <Separator />

      {/* Language selector */}
      <div>
        <h3 className="text-sm font-medium">
          {t('settings.language.label')}
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          {t('settings.language.description')}
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          {SUPPORTED_LANGUAGES.map((lang) => (
            <button
              key={lang.code}
              onClick={() => switchLang(lang.code)}
              className={
                'rounded-lg border px-3 py-2 text-left text-sm transition-colors ' +
                (locale === lang.code
                  ? 'border-primary bg-primary/5 text-primary font-medium'
                  : 'border-border hover:bg-muted')
              }
            >
              {lang.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
