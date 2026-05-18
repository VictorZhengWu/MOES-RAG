/**
 * General settings tab: theme selector and interface language dropdown.
 *
 * Theme switching is implemented now — toggles 'dark' class on <html>.
 * 'system' follows the OS preference via matchMedia listener.
 * Language uses a dropdown select matching the DeepSeek UX pattern.
 */

'use client';

import { useEffect, useCallback } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { useRouter, usePathname } from 'next/navigation';
import { SUPPORTED_LANGUAGES, type SupportedLanguage } from '@/types';
import { Separator } from '@/components/ui/separator';
import { Sun, Moon, Monitor } from 'lucide-react';

type Theme = 'light' | 'dark' | 'system';

interface Props {
  theme: Theme;
  onThemeChange: (theme: Theme) => void;
}

/**
 * Apply theme by toggling 'dark' class on <html>.
 *
 * WHY: Tailwind's dark mode is class-based. Toggling the class
 * switches all dark: variants instantly. For 'system', we listen
 * to the OS-level prefers-color-scheme media query.
 */
function applyTheme(t: Theme) {
  const root = document.documentElement;
  if (t === 'dark') {
    root.classList.add('dark');
  } else if (t === 'light') {
    root.classList.remove('dark');
  } else {
    // system
    const isDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    root.classList.toggle('dark', isDark);
  }
}

export function GeneralTab({ theme, onThemeChange }: Props) {
  const t = useTranslations();
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  // Apply theme on mount and when it changes
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // Listen for system theme changes when in 'system' mode
  useEffect(() => {
    if (theme !== 'system') return;
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = () => applyTheme('system');
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [theme]);

  const switchLang = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const lang = e.target.value as SupportedLanguage;
      const segments = pathname.split('/').filter(Boolean);
      if (['en', 'zh', 'ko', 'ja', 'no', 'ms'].includes(segments[0])) {
        segments[0] = lang;
      } else {
        segments.unshift(lang);
      }
      router.push('/' + segments.join('/'));
    },
    [pathname, router],
  );

  const themes: { key: Theme; icon: typeof Sun; label: string }[] = [
    { key: 'light', icon: Sun, label: t('settings.theme.light') },
    { key: 'dark', icon: Moon, label: t('settings.theme.dark') },
    { key: 'system', icon: Monitor, label: t('settings.theme.system') },
  ];

  return (
    <div className="space-y-6">
      {/* Theme selector — 3 clickable cards */}
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

      {/* Language selector — dropdown like DeepSeek */}
      <div>
        <h3 className="text-sm font-medium">
          {t('settings.language.label')}
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          {t('settings.language.description')}
        </p>
        <select
          value={locale}
          onChange={switchLang}
          className="mt-3 w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:border-primary focus:ring-1 focus:ring-primary"
        >
          {SUPPORTED_LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
