/**
 * Admin sidebar navigation — 6 sections + language switcher at bottom.
 */

'use client';

import { useRouter, usePathname } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { LanguageSwitcher } from './language-switcher';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard, FileText, Share2, Cpu, Users, Activity,
  Settings, HelpCircle, ArrowLeft,
} from 'lucide-react';

const NAV_ITEMS = [
  { id: 'dashboard', href: '/admin', icon: LayoutDashboard },
  { id: 'documents', href: '/admin/documents', icon: FileText },
  { id: 'knowledgeGraph', href: '/admin/knowledge-graph', icon: Share2 },
  { id: 'llmConfig', href: '/admin/llm-config', icon: Cpu },
  { id: 'users', href: '/admin/users', icon: Users },
  { id: 'monitoring', href: '/admin/monitoring', icon: Activity },
];

export function AdminSidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();
  const t = useTranslations();

  const isActive = (href: string) => {
    const fullHref = `/${locale}${href}`;
    return pathname === fullHref || pathname.startsWith(fullHref + '/');
  };

  return (
    <aside className="flex h-full w-[220px] shrink-0 flex-col border-r bg-muted/20">
      {/* Brand header */}
      <button
        onClick={() => router.push(`/${locale}/admin`)}
        className="flex items-center gap-2 px-4 py-4 border-b hover:bg-muted/30 transition-colors"
      >
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-primary-foreground text-xs font-bold">
          MO
        </div>
        <span className="text-sm font-semibold">{t('app.shortName')}</span>
      </button>

      {/* Navigation items */}
      <nav className="flex-1 space-y-0.5 p-3">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const active = isActive(item.href);
          return (
            <button
              key={item.id}
              onClick={() => router.push(`/${locale}${item.href}`)}
              className={cn(
                'flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors',
                active
                  ? 'bg-accent text-foreground font-medium'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              <Icon className="h-4 w-4" />
              {t(`nav.${item.id}`)}
            </button>
          );
        })}
      </nav>

      {/* Bottom section */}
      <div className="border-t p-3 space-y-1">
        <button
          onClick={() => router.push(`/${locale}/admin/settings`)}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <Settings className="h-4 w-4" />
          {t('nav.settings')}
        </button>
        <button
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <HelpCircle className="h-4 w-4" />
          {t('nav.help')}
        </button>
        <LanguageSwitcher />
        <a
          href={`/${locale}/chat`}
          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('nav.backToChat')}
        </a>
      </div>
    </aside>
  );
}
