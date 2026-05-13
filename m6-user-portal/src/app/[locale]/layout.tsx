/**
 * Locale-scoped layout. Provides next-intl provider for all pages
 * under /[locale]/. The actual AppLayout (sidebar + header + content)
 * will be added in Task B8.
 *
 * WHY: Separating the i18n provider from the UI layout allows the
 * (auth) route group (login/register) to use a different visual
 * layout while still receiving i18n messages.
 */
import { NextIntlClientProvider } from 'next-intl';
import { getMessages } from 'next-intl/server';

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  const messages = await getMessages();

  return (
    <NextIntlClientProvider locale={locale} messages={messages}>
      {children}
    </NextIntlClientProvider>
  );
}
