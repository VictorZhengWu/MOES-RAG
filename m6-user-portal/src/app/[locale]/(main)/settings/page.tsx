/**
 * Settings page — opens the settings dialog automatically.
 *
 * WHY: The settings dialog is the primary settings UI. When the user
 * navigates to /settings, the dialog opens immediately. Closing it
 * redirects back to /chat.
 */

'use client';

import { useRouter } from 'next/navigation';
import { useLocale } from 'next-intl';
import { SettingsDialog } from '@/components/settings/settings-dialog';

export default function SettingsPage() {
  const router = useRouter();
  const locale = useLocale();

  const handleClose = () => {
    router.push(`/${locale}/chat`);
  };

  return <SettingsDialog open={true} onClose={handleClose} />;
}
