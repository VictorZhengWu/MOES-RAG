/**
 * Client wrapper: AuthGuard → AdminLayout → children.
 */

'use client';

import { AuthGuard } from './auth-guard';
import { AdminLayout } from './admin-layout';

export function AdminAuthWrapper({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AdminLayout>{children}</AdminLayout>
    </AuthGuard>
  );
}
