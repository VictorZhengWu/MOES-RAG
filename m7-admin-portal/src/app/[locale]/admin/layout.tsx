/**
 * Admin route group layout — Auth Guard → AdminLayout.
 */

import { AdminAuthWrapper } from '@/components/layout/admin-auth-wrapper';

export default function AdminRouteLayout({ children }: { children: React.ReactNode }) {
  return <AdminAuthWrapper>{children}</AdminAuthWrapper>;
}
