/**
 * Settings dialog with tabbed navigation (General / Profile / About).
 *
 * WHY: DeepSeek-style settings: a dialog with a left sidebar of tabs
 * (with icons) and a right content area. The dialog has a fixed height
 * so switching tabs doesn't cause layout jumps. The title bar shows
 * the active tab name, not a static "Settings" label.
 */

'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { useSettingsStore } from '@/lib/stores/settings-store';
import { GeneralTab } from './general-tab';
import { ProfileTab } from './profile-tab';
import { AboutTab } from './about-tab';
import { Button } from '@/components/ui/button';
import { Settings, User, Info, X } from 'lucide-react';

type TabId = 'general' | 'profile' | 'about';

interface Props {
  open: boolean;
  onClose: () => void;
}

const TAB_ICONS: Record<TabId, typeof Settings> = {
  general: Settings,
  profile: User,
  about: Info,
};

export function SettingsDialog({ open, onClose }: Props) {
  const t = useTranslations();
  const [activeTab, setActiveTab] = useState<TabId>('general');
  const { theme, setTheme } = useSettingsStore();

  if (!open) return null;

  const tabs: { id: TabId; icon: typeof Settings }[] = [
    { id: 'general', icon: TAB_ICONS.general },
    { id: 'profile', icon: TAB_ICONS.profile },
    { id: 'about', icon: TAB_ICONS.about },
  ];

  const activeTabLabel = t(`settings.tabs.${activeTab}`);

  return (
    // Backdrop — clicking outside closes
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[10vh] bg-black/20"
      onClick={onClose}
    >
      {/* Dialog — fixed height, no layout jumps between tabs */}
      <div
        className="flex w-[680px] h-[440px] rounded-xl border bg-background shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Left: Tab sidebar with icons */}
        <div className="w-44 shrink-0 border-r bg-muted/20 p-3">
          <div className="space-y-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <Button
                  key={tab.id}
                  variant={activeTab === tab.id ? 'secondary' : 'ghost'}
                  className="w-full justify-start gap-2 text-sm h-8"
                  onClick={() => setActiveTab(tab.id)}
                >
                  <Icon className="h-4 w-4" />
                  {t(`settings.tabs.${tab.id}`)}
                </Button>
              );
            })}
          </div>
        </div>

        {/* Right: Content area */}
        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Header — shows active tab name, not "Settings" */}
          <div className="flex items-center justify-between border-b px-4 py-3 shrink-0">
            <h2 className="text-sm font-semibold">{activeTabLabel}</h2>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={onClose}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* Tab content — fills remaining height */}
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
