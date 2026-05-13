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
import { Button } from '@/components/ui/button';
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
    const newPath = pathname.replace(`/${locale}`, `/${newLocale}`);
    router.push(newPath);
  };

  const current = SUPPORTED_LANGUAGES.find((l) => l.code === locale);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger>
        <Button variant="ghost" size="sm" className="text-xs">
          {current?.label ?? 'English'}
        </Button>
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
