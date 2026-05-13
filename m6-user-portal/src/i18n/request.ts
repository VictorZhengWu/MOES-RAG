/**
 * next-intl request configuration for App Router.
 *
 * WHY: next-intl requires this configuration file in App Router mode.
 * It loads the correct locale messages based on the request's locale
 * parameter (set by middleware.ts). The getRequestConfig function runs
 * on every request in Server Components.
 */
import { getRequestConfig } from 'next-intl/server';

export default getRequestConfig(async ({ requestLocale }) => {
  let locale = await requestLocale;
  if (!locale || !['en', 'zh', 'ko', 'ja', 'no'].includes(locale)) {
    locale = 'en';
  }
  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
