/**
 * Root page: redirects / to /en (default locale).
 * The middleware handles locale detection; this is a fallback.
 */
import { redirect } from 'next/navigation';

export default function Home() {
  redirect('/en');
}
