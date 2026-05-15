/**
 * About tab: developer info, social media, license, donation.
 *
 * WHY: Users and potential contributors need to know who built this
 * and how to connect. Social links and donation info support the
 * open-source / community aspect of the project.
 */

import { Separator } from '@/components/ui/separator';
import { Globe, Heart } from 'lucide-react';

interface SocialLink {
  label: string;
  url: string;
}

const socials: SocialLink[] = [
  { label: 'X (Twitter)', url: 'https://x.com/victor_zheng' },
  { label: 'YouTube', url: 'https://youtube.com/@victorzheng' },
  { label: 'Facebook', url: 'https://facebook.com/victorzheng' },
  { label: 'WeChat', url: 'https://weixin.qq.com' },
];

export function AboutTab() {
  return (
    <div className="space-y-6">
      {/* Developer */}
      <div>
        <h3 className="text-sm font-medium">Developer</h3>
        <p className="mt-1 text-sm">Victor Zheng / 郑武</p>
        <p className="text-xs text-muted-foreground">
          Ship & Offshore Engineering · Software Development
        </p>
      </div>

      <Separator />

      {/* Social media */}
      <div>
        <h3 className="text-sm font-medium">Connect</h3>
        <div className="mt-2 space-y-1">
          {socials.map((s) => (
            <a
              key={s.label}
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-primary transition-colors"
            >
              <Globe className="h-3.5 w-3.5" />
              {s.label}
            </a>
          ))}
        </div>
      </div>

      <Separator />

      {/* License */}
      <div>
        <h3 className="text-sm font-medium">License</h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Proprietary Software. All rights reserved.
        </p>
      </div>

      <Separator />

      {/* Donation */}
      <div>
        <h3 className="text-sm font-medium">Support This Project</h3>
        <p className="mt-1 text-xs text-muted-foreground">
          If you find this system useful, consider supporting its
          continued development and maintenance.
        </p>
        <a
          href="https://ko-fi.com/victorzheng"
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <Heart className="h-4 w-4" />
          Donate
        </a>
      </div>
    </div>
  );
}
