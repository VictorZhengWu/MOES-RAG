/**
 * Next.js configuration with next-intl plugin.
 *
 * WHY: next-intl 4.x for App Router requires wrapping the Next.js
 * config with createNextIntlPlugin(). This plugin discovers the
 * i18n/request.ts config file and enables getMessages() and other
 * next-intl APIs in Server Components.
 */
import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const nextConfig: NextConfig = {
  /* config options here */
};

const withNextIntl = createNextIntlPlugin();
export default withNextIntl(nextConfig);
