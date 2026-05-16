/**
 * Language switcher for admin sidebar.
 * Same logic as M6: splits path, replaces locale segment.
 */

'use client';

import { useRouter, usePathname } from 'next/navigation';
import { useLocale } from 'next-intl';
import { SUPPORTED_LANGUAGES } from '@/types';

export function LanguageSwitcher() {
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();

  const switchTo = (newLocale: string) => {
    const segments = pathname.split('/').filter(Boolean);
    if (['en', 'zh', 'ko', 'ja', 'no'].includes(segments[0])) {
      segments[0] = newLocale;
    } else {
      segments.unshift(newLocale);
    }
    router.push('/' + segments.join('/'));
  };

  return (
    <select
      value={locale}
      onChange={(e) => switchTo(e.target.value)}
      className="w-full rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
    >
      {SUPPORTED_LANGUAGES.map((lang) => (
        <option key={lang.code} value={lang.code}>{lang.label}</option>
      ))}
    </select>
  );
}
