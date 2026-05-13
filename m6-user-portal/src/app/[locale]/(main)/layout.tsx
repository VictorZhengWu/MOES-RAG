/**
 * (main) route group layout.
 *
 * WHY: Route groups ((main)) allow different layouts for different
 * sections without affecting the URL. All main app pages (chat,
 * knowledge, settings) share this layout which will wrap them
 * with the AppLayout (sidebar + header) in Task B8.
 *
 * Currently a pass-through — AppLayout will be added in Task B8.
 */

export default function MainLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
