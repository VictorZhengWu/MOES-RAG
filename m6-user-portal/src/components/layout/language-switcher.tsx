/**
 * Language switcher dropdown in the header bar.
 *
 * WHY: Instant switch without page reload via next-intl's router.push.
 * Changing the locale in the URL path triggers a client-side navigation
 * that re-renders all translated strings immediately. The current locale
 * is highlighted in bold in the dropdown.
 */

'use client';

import { useRouter, usePathname } from 'next/navigation';
import { useLocale } from 'next-intl';
import { SUPPORTED_LANGUAGES } from '@/types';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export function LanguageSwitcher() {
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();

  const switchTo = (newLocale: string) => {
    // usePathname() from next/navigation returns the FULL path including
    // locale prefix (e.g., /en/chat). We replace the first segment.
    const segments = pathname.split('/').filter(Boolean);     // ['en', 'chat']
    if (['en', 'zh', 'ko', 'ja', 'no'].includes(segments[0])) {
      segments[0] = newLocale;                                 // ['zh', 'chat']
    } else {
      segments.unshift(newLocale);                             // fallback
    }
    router.push('/' + segments.join('/'));                     // /zh/chat
  };

  const current = SUPPORTED_LANGUAGES.find((l) => l.code === locale);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="inline-flex items-center justify-center rounded-lg px-2.5 h-7 text-xs font-medium hover:bg-muted transition-colors"
      >
        {current?.label ?? 'English'}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {SUPPORTED_LANGUAGES.map((lang) => (
          <DropdownMenuItem
            key={lang.code}
            onClick={() => switchTo(lang.code)}
            className={locale === lang.code ? 'font-bold' : ''}
          >
            {lang.label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
