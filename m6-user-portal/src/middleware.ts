/**
 * next-intl middleware: intercepts requests without locale prefix and
 * redirects to the appropriate locale (/en, /zh, /ko, /ja, /no, /ms).
 *
 * WHY: Path-based locale routing enables SEO-friendly URLs and makes
 * language switching a simple client-side navigation. The middleware
 * reads the Accept-Language header and falls back to 'en'.
 */
import createMiddleware from 'next-intl/middleware';

export default createMiddleware({
  locales: ['en', 'zh', 'ko', 'ja', 'no', 'ms'],
  defaultLocale: 'en',
  localeDetection: true,
});

export const config = { matcher: ['/((?!_next|api|favicon.ico|.*\\.).*)'] };
