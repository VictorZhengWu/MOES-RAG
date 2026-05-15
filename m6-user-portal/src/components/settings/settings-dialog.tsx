/**
 * Settings dialog with tabbed navigation (General / Profile / About).
 *
 * WHY: DeepSeek-style settings: a dialog with a left sidebar of tabs
 * and a right content area. The dialog opens via the Settings button
 * in the sidebar. Language switching is now exclusively in this
 * dialog under the General tab.
 */

'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { useSettingsStore } from '@/lib/stores/settings-store';
import { GeneralTab } from './general-tab';
import { ProfileTab } from './profile-tab';
import { AboutTab } from './about-tab';
import { Button } from '@/components/ui/button';
import { X } from 'lucide-react';

type TabId = 'general' | 'profile' | 'about';

interface Props {
  open: boolean;
  onClose: () => void;
}

const TABS: { id: TabId; labelKey: string }[] = [
  { id: 'general', labelKey: 'General' },
  { id: 'profile', labelKey: 'Profile' },
  { id: 'about', labelKey: 'About' },
];

export function SettingsDialog({ open, onClose }: Props) {
  const t = useTranslations();
  const [activeTab, setActiveTab] = useState<TabId>('general');
  const { theme, setTheme } = useSettingsStore();

  if (!open) return null;

  return (
    // Backdrop — clicking outside closes
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] bg-black/20"
      onClick={onClose}
    >
      {/* Dialog — click inside does NOT close */}
      <div
        className="flex w-[680px] max-h-[75vh] rounded-xl border bg-background shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Left: Tab sidebar */}
        <div className="w-44 shrink-0 border-r bg-muted/20 p-3">
          <div className="space-y-1">
            {TABS.map((tab) => (
              <Button
                key={tab.id}
                variant={activeTab === tab.id ? 'secondary' : 'ghost'}
                className="w-full justify-start text-sm h-8"
                onClick={() => setActiveTab(tab.id)}
              >
                {tab.labelKey}
              </Button>
            ))}
          </div>
        </div>

        {/* Right: Content area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Header with close button */}
          <div className="flex items-center justify-between border-b px-4 py-3 shrink-0">
            <h2 className="text-sm font-semibold">{t('settings.title')}</h2>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={onClose}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Tab content */}
          <div className="flex-1 overflow-y-auto p-4">
            {activeTab === 'general' && (
              <GeneralTab theme={theme} onThemeChange={setTheme} />
            )}
            {activeTab === 'profile' && <ProfileTab />}
            {activeTab === 'about' && <AboutTab />}
          </div>
        </div>
      </div>
    </div>
  );
}
