/**
 * Admin sidebar — collapsible (expand/collapse toggle).
 * Language switching is in Settings, not here.
 * Admin login state at the bottom.
 */

'use client';

import { useRouter, usePathname } from 'next/navigation';
import { useTranslations, useLocale } from 'next-intl';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard, FileText, Share2, Cpu, Users, Activity,
  Settings, HelpCircle, ArrowLeft, PanelLeftClose, PanelLeft,
  LogIn,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';

const NAV_ITEMS = [
  { id: 'dashboard', href: '/admin', icon: LayoutDashboard },
  { id: 'documents', href: '/admin/documents', icon: FileText },
  { id: 'knowledgeGraph', href: '/admin/knowledge-graph', icon: Share2 },
  { id: 'llmConfig', href: '/admin/llm-config', icon: Cpu },
  { id: 'users', href: '/admin/users', icon: Users },
  { id: 'monitoring', href: '/admin/monitoring', icon: Activity },
];

interface Props {
  collapsed: boolean;
  onToggle: () => void;
}

export function AdminSidebar({ collapsed, onToggle }: Props) {
  const router = useRouter();
  const pathname = usePathname();
  const locale = useLocale();
  const t = useTranslations();

  const isActive = (href: string) => {
    const fullHref = `/${locale}${href}`;
    return pathname === fullHref || pathname.startsWith(fullHref + '/');
  };

  // Collapsed: icon-only strip
  if (collapsed) {
    return (
      <aside className="flex h-full w-[56px] shrink-0 flex-col items-center border-r bg-muted/20 py-3 gap-2">
        <button onClick={onToggle} className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted" title="Expand">
          <PanelLeft className="h-4 w-4 text-muted-foreground" />
        </button>
        <Separator className="w-8" />
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              onClick={() => router.push(`/${locale}${item.href}`)}
              className={cn(
                'flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted',
                isActive(item.href) ? 'bg-accent text-foreground' : 'text-muted-foreground',
              )}
              title={t(`nav.${item.id}`)}
            >
              <Icon className="h-4 w-4" />
            </button>
          );
        })}
        <div className="flex-1" />
        <button onClick={() => router.push(`/${locale}/admin/settings`)} className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted text-muted-foreground" title={t('nav.settings')}>
          <Settings className="h-4 w-4" />
        </button>
        <button onClick={() => router.push(`/${locale}/login`)} className="flex h-9 w-9 items-center justify-center rounded-lg hover:bg-muted text-muted-foreground" title="Log in">
          <LogIn className="h-4 w-4" />
        </button>
      </aside>
    );
  }

  // Expanded: full sidebar
  return (
    <aside className="flex h-full w-[220px] shrink-0 flex-col border-r bg-muted/20">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b">
        <button onClick={() => router.push(`/${locale}/admin`)} className="flex items-center gap-2 hover:opacity-80">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-primary-foreground text-xs font-bold">MO</div>
          <span className="text-sm font-semibold">{t('app.shortName')}</span>
        </button>
        <Button variant="ghost" size="icon" className="h-7 w-7 ml-auto" onClick={onToggle} title="Collapse">
          <PanelLeftClose className="h-4 w-4" />
        </Button>
      </div>

      {/* Nav */}
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
                active ? 'bg-accent text-foreground font-medium' : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
            >
              <Icon className="h-4 w-4" />
              {t(`nav.${item.id}`)}
            </button>
          );
        })}
      </nav>

      {/* Bottom */}
      <div className="border-t p-3 space-y-1">
        <button onClick={() => router.push(`/${locale}/admin/settings`)} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors">
          <Settings className="h-4 w-4" />{t('nav.settings')}
        </button>
        <button className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors">
          <HelpCircle className="h-4 w-4" />{t('nav.help')}
        </button>
        <Separator className="my-2" />
        <a href={`/${locale}/chat`} className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground transition-colors">
          <ArrowLeft className="h-4 w-4" />{t('nav.backToChat')}
        </a>
        <Separator className="my-2" />
        <Button variant="outline" className="w-full justify-start gap-2 h-9 text-sm" onClick={() => router.push(`/${locale}/login`)}>
          <LogIn className="h-4 w-4" />Log in
        </Button>
      </div>
    </aside>
  );
}
