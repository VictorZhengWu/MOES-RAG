/**
 * Admin layout: sidebar (left) + content area (right).
 */

'use client';

import { AdminSidebar } from './admin-sidebar';

export function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <AdminSidebar />
      <main className="flex-1 overflow-y-auto bg-background">
        {children}
      </main>
    </div>
  );
}
