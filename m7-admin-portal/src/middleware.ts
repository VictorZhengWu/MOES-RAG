import createMiddleware from 'next-intl/middleware';
export default createMiddleware({
  locales: ['en', 'zh', 'ko', 'ja', 'no'],
  defaultLocale: 'en',
  localeDetection: true,
});
export const config = { matcher: ['/((?!_next|api|favicon.ico|.*\\.).*)'] };
