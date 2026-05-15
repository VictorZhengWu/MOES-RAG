/**
 * Social login buttons: Google, Microsoft, Apple, Facebook, X, WeChat.
 *
 * WHY: Users expect OAuth options. Phase 1 shows styled buttons that
 * log a message; Phase 2 will implement real OAuth flows via the
 * backend. Icons are inline SVGs for zero dependencies.
 */

'use client';

import { Button } from '@/components/ui/button';

interface SocialProvider {
  id: string;
  label: string;
  icon: React.ReactNode;
  bgClass: string;
}

const GoogleIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4">
    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
  </svg>
);

const MicrosoftIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4">
    <rect x="1" y="1" width="10" height="10" fill="#F25022"/>
    <rect x="13" y="1" width="10" height="10" fill="#7FBA00"/>
    <rect x="1" y="13" width="10" height="10" fill="#00A4EF"/>
    <rect x="13" y="13" width="10" height="10" fill="#FFB900"/>
  </svg>
);

const AppleIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
    <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/>
  </svg>
);

const FacebookIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4">
    <path fill="#1877F2" d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
  </svg>
);

const XIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="currentColor">
    <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
  </svg>
);

const WeChatIcon = () => (
  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="#07C160">
    <path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.78 7.011c.56 0 1.008.456 1.008 1.003 0 .556-.449 1.01-1.008 1.01-.559 0-1.007-.454-1.007-1.01 0-.547.448-1.003 1.007-1.003zm5.847 1.998c-.55 0-.998-.454-.998-1.004 0-.547.448-1.003.998-1.003.548 0 .998.456.998 1.003 0 .55-.45 1.004-.998 1.004z"/>
    <path d="M15.262 14.094c-3.203 0-5.81 2.332-5.81 5.197 0 2.874 2.607 5.206 5.81 5.206.45 0 .891-.04 1.322-.12l1.574.851a.22.22 0 0 0 .11.034c.105 0 .19-.085.19-.188 0-.047-.02-.094-.03-.14l-.255-.945a.44.44 0 0 1 .16-.44c1.63-1.094 2.553-2.603 2.553-4.258 0-2.865-2.608-5.197-5.811-5.197zm-2.426 3.96c.355 0 .642.282.642.63a.636.636 0 0 1-.642.63.636.636 0 0 1-.642-.63c0-.348.287-.63.642-.63zm4.847 0c.355 0 .642.282.642.63a.636.636 0 0 1-.642.63.636.636 0 0 1-.642-.63c0-.348.287-.63.642-.63z"/>
  </svg>
);

const SOCIAL_PROVIDERS: SocialProvider[] = [
  { id: 'google', label: 'Google', icon: <GoogleIcon />, bgClass: 'hover:bg-red-50 dark:hover:bg-red-950' },
  { id: 'microsoft', label: 'Microsoft', icon: <MicrosoftIcon />, bgClass: 'hover:bg-orange-50 dark:hover:bg-orange-950' },
  { id: 'apple', label: 'Apple', icon: <AppleIcon />, bgClass: 'hover:bg-gray-100 dark:hover:bg-gray-800' },
  { id: 'facebook', label: 'Facebook', icon: <FacebookIcon />, bgClass: 'hover:bg-blue-50 dark:hover:bg-blue-950' },
  { id: 'x', label: 'X', icon: <XIcon />, bgClass: 'hover:bg-neutral-100 dark:hover:bg-neutral-800' },
  { id: 'wechat', label: 'WeChat', icon: <WeChatIcon />, bgClass: 'hover:bg-green-50 dark:hover:bg-green-950' },
];

export function SocialButtons() {
  const handleSocialLogin = (provider: string) => {
    // Phase 2: redirect to OAuth flow
    console.log(`Social login: ${provider}`);
  };

  return (
    <div className="grid grid-cols-3 gap-2">
      {SOCIAL_PROVIDERS.map((p) => (
        <Button
          key={p.id}
          variant="outline"
          size="sm"
          className={`flex items-center justify-center gap-1.5 h-9 text-xs ${p.bgClass}`}
          onClick={() => handleSocialLogin(p.id)}
        >
          {p.icon}
          <span className="hidden sm:inline">{p.label}</span>
        </Button>
      ))}
    </div>
  );
}
