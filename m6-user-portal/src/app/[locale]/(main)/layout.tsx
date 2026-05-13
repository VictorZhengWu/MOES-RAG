/**
 * (main) route group layout.
 *
 * WHY: Route groups ((main)) allow different layouts for different
 * sections without affecting the URL. All main app pages (chat,
 * knowledge, settings) share this layout which wraps them with
 * the AppLayout (sidebar + header + jump nav).
 *
 * The auth pages (login, register) under (auth) use a different
 * layout without the sidebar.
 */

import { AppLayoutWrapper } from '@/components/layout/app-layout-wrapper';

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AppLayoutWrapper>{children}</AppLayoutWrapper>;
}
