/**
 * Main app layout: sidebar (collapsible) + content + citation panel.
 *
 * Layout:
 * ┌──────────┬──────────────────────┬────┬──────────────┐
 * │ Sidebar  │  Chat Messages       │Jump│ Citation     │
 * │ 260px    │  flex-1              │Nav │ Panel        │
 * │ (or 0)   │                      │48px│ 420px (or 0) │
 * └──────────┴──────────────────────┴────┴──────────────┘
 *
 * WHY: The citation panel must NOT overlay content. When it opens,
 * the middle content area shrinks to accommodate it — just like
 * DeepSeek's reference panel. On narrow viewports, the sidebar
 * auto-hides first; on very narrow viewports, the citation
 * panel yields to content.
 */

'use client';

import { useEffect, useState } from 'react';
import { ConversationSidebar } from '@/components/conversation/conversation-sidebar';
import { JumpNavigation } from '@/components/navigation/jump-navigation';
import { CitationPanel } from '@/components/chat/citation-panel';
import { useChatStore } from '@/lib/stores/chat-store';
import { useTranslations } from 'next-intl';
import { PanelLeftClose, PanelLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

const SIDEBAR_WIDTH = 260;
const CITATION_PANEL_WIDTH = 420;

export function AppLayout({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [viewportNarrow, setViewportNarrow] = useState(false);
  const t = useTranslations();
  const citationOpen = useChatStore((s) => s.selectedCitationIndex !== null);

  // Auto-collapse sidebar on narrow viewports
  useEffect(() => {
    const check = () => setViewportNarrow(window.innerWidth < 1024);
    check();
    window.addEventListener('resize', check);
    return () => window.removeEventListener('resize', check);
  }, []);

  // On narrow viewports, keep sidebar collapsed
  const sidebarVisible = sidebarOpen && !viewportNarrow;

  return (
    <div className="flex h-screen overflow-hidden">
      {/* ── Left Sidebar ── */}
      <div
        className={
          'transition-all duration-200 ease-in-out overflow-hidden border-r bg-muted/30 flex flex-col shrink-0 ' +
          (sidebarVisible ? 'w-[260px]' : 'w-0 border-r-0')
        }
      >
        {sidebarVisible && <ConversationSidebar />}
      </div>

      {/* ── Middle: Content Area ── */}
      <div className="flex flex-1 flex-col overflow-hidden min-w-0">
        {/* Top bar */}
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
        </header>

        {/* Chat + jump nav */}
        <div className="flex flex-1 overflow-hidden min-h-0">
          <main className="flex-1 overflow-y-auto">{children}</main>
          <JumpNavigation />
        </div>
      </div>

      {/* ── Right: Citation Panel (third column, NOT an overlay) ── */}
      <div
        className={
          'transition-all duration-200 ease-in-out overflow-hidden border-l bg-background shrink-0 ' +
          (citationOpen ? 'w-[420px]' : 'w-0 border-l-0')
        }
      >
        <CitationPanel />
      </div>
    </div>
  );
}
