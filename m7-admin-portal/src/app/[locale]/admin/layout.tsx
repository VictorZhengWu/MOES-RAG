/**
 * Admin route group layout — wraps all /admin/* pages with AdminLayout.
 * AdminLayout has its own sidebar, independent of the main app layout.
 */

import { AdminLayoutWrapper } from '@/components/layout/admin-layout-wrapper';

export default function AdminRouteLayout({ children }: { children: React.ReactNode }) {
  return <AdminLayoutWrapper>{children}</AdminLayoutWrapper>;
}
