/**
 * Auth Guard for M7 admin pages.
 *
 * WHAT: Replaces mock username/password login with real M8 API key
 *       validation. Only users with admin/editor role can access.
 *
 * WHY: Phase 1 used hardcoded credentials. Phase 3 uses the same M8
 *      auth system as M6 — the API key is validated against the real
 *      user database and the is_admin flag is checked.
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Shield } from 'lucide-react';

const AUTH_KEY_STORAGE = 'm7-admin-auth';
const USER_KEY_STORAGE = 'm7-admin-user';
const TOKEN_KEY_STORAGE = 'm7-admin-token';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentUser, setCurrentUser] = useState('');

  useEffect(() => {
    const stored = sessionStorage.getItem(AUTH_KEY_STORAGE);
    const user = sessionStorage.getItem(USER_KEY_STORAGE) || '';
    setAuthed(stored === 'true');
    setCurrentUser(user);
  }, []);

  const handleLogin = async () => {
    if (!apiKey.trim()) {
      setError('Please enter your API key.');
      return;
    }
    setLoading(true);
    setError('');

    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
      const res = await fetch(`${baseUrl}/auth/admin-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey.trim() }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || `Login failed (${res.status})`);
        return;
      }

      const data = await res.json();
      sessionStorage.setItem(AUTH_KEY_STORAGE, 'true');
      sessionStorage.setItem(USER_KEY_STORAGE, data.username);
      sessionStorage.setItem(TOKEN_KEY_STORAGE, data.api_key);
      setAuthed(true);
      setCurrentUser(data.username);
    } catch {
      setError('Cannot reach the server. Is M8 running on port 8000?');
    } finally {
      setLoading(false);
    }
  };

  if (authed === null) return null;

  if (!authed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/20">
        <div className="w-full max-w-sm space-y-5 rounded-xl border bg-background p-8 shadow-lg">
          <div className="text-center">
            <Shield className="mx-auto h-10 w-10 text-primary mb-2" />
            <h1 className="text-xl font-bold">Admin Login</h1>
            <p className="text-sm text-muted-foreground mt-1">
              Enter your M8 API key to access the admin panel.
            </p>
          </div>
          <Input
            value={apiKey}
            onChange={(e) => { setApiKey(e.target.value); setError(''); }}
            onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            placeholder="sk-m8-xxxxxxxxxxxxxxxx"
            type="password"
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button className="w-full" onClick={handleLogin} disabled={loading}>
            {loading ? 'Verifying...' : 'Sign In'}
          </Button>
          <p className="text-xs text-muted-foreground text-center">
            Use the same API key from your M6 account. Admin/editor role required.
          </p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
