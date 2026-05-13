/**
 * Client-side wrapper for AppLayout.
 *
 * WHY: Next.js App Router layouts are Server Components by default.
 * AppLayout uses 'use client' hooks (useState, useTranslations),
 * so we need this thin client wrapper to bridge the gap.
 */

'use client';

import { AppLayout } from './app-layout';

export function AppLayoutWrapper({ children }: { children: React.ReactNode }) {
  return <AppLayout>{children}</AppLayout>;
}
