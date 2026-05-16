/**
 * Client wrapper for AdminLayout.
 * Next.js layouts are Server Components by default;
 * AdminLayout uses 'use client' hooks so needs this bridge.
 */

'use client';

import { AdminLayout } from './admin-layout';

export function AdminLayoutWrapper({ children }: { children: React.ReactNode }) {
  return <AdminLayout>{children}</AdminLayout>;
}
