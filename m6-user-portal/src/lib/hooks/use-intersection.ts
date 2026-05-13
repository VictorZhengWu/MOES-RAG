/**
 * Intersection Observer hook for scroll-based loading triggers.
 *
 * WHY: The conversation sidebar may have many items when real M5
 * returns paginated results. This hook provides infinite-scroll
 * loading capability. Currently the mock API returns all
 * conversations at once, so this is forward-looking infrastructure.
 */

'use client';

import { useEffect, useRef, useState } from 'react';

export function useIntersection(
  options?: IntersectionObserverInit,
): [React.RefObject<HTMLDivElement | null>, boolean] {
  const ref = useRef<HTMLDivElement | null>(null);
  const [isIntersecting, setIsIntersecting] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const observer = new IntersectionObserver(([entry]) => {
      setIsIntersecting(entry.isIntersecting);
    }, options);

    observer.observe(el);
    return () => observer.disconnect();
  }, [options]);

  return [ref, isIntersecting];
}
