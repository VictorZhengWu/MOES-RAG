/**
 * Main app layout with collapsible sidebar.
 *
 * Layout (3 columns when sidebar expanded):
 * ┌──────────┬──────────────────────┬──────────┐
 * │ Sidebar  │  Chat Messages       │ Jump Nav │
 * │ 260px    │  flex-1              │  48px    │
 * └──────────┴──────────────────────┴──────────┘
 *
 * Collapsed: sidebar width → 0 (hidden).
 *
 * WHY: Professional users need maximum reading space for long
 * regulation excerpts. The collapsible sidebar gives them control.
 * The toggle button is in the header bar for easy access.
 */

'use client';

import { useState } from 'react';
import { ConversationSidebar } from '@/components/conversation/conversation-sidebar';
import { JumpNavigation } from '@/components/navigation/jump-navigation';
import { CitationPanel } from '@/components/chat/citation-panel';
import { LanguageSwitcher } from './language-switcher';
import { useTranslations } from 'next-intl';
import { PanelLeftClose, PanelLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const t = useTranslations();

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Collapsible Sidebar */}
      <div
        className={
          'transition-all duration-200 ease-in-out overflow-hidden border-r bg-muted/30 flex flex-col ' +
          (sidebarOpen ? 'w-[260px]' : 'w-0 border-r-0')
        }
      >
        {sidebarOpen && <ConversationSidebar />}
      </div>

      {/* Main Content Area */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Top bar: collapse toggle + app name + language switcher */}
        <header className="flex h-11 items-center justify-between border-b px-3 shrink-0">
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              onClick={() => setSidebarOpen(!sidebarOpen)}
              title={sidebarOpen ? t('sidebar.collapse') : t('sidebar.expand')}
            >
              {sidebarOpen ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeft className="h-4 w-4" />
              )}
            </Button>
            <span className="text-sm font-semibold">{t('app.shortName')}</span>
          </div>
          <LanguageSwitcher />
        </header>

        {/* Chat content + right jump nav */}
        <div className="flex flex-1 overflow-hidden">
          <main className="flex-1 overflow-y-auto">{children}</main>
          <JumpNavigation />
        </div>
      </div>

      {/* Citation Panel (right-side sheet, overlays when open) */}
      <CitationPanel />
    </div>
  );
}
