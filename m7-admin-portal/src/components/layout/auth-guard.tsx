/**
 * Auth Guard for M7 admin pages.
 * Phase 1: simple password check via localStorage.
 * Phase 2: real JWT/OAuth admin authentication.
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Shield } from 'lucide-react';

const AUTH_KEY = 'm7-admin-auth';

// Phase 1: simple password
const ADMIN_PASSWORD = 'admin';

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const stored = localStorage.getItem(AUTH_KEY);
    setAuthed(stored === 'true');
  }, []);

  const handleLogin = () => {
    if (password === ADMIN_PASSWORD) {
      localStorage.setItem(AUTH_KEY, 'true');
      setAuthed(true);
      setError('');
    } else {
      setError('Incorrect password.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(AUTH_KEY);
    setAuthed(false);
  };

  // Loading state
  if (authed === null) return null;

  // Not authenticated — show login
  if (!authed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/20">
        <div className="w-full max-w-sm space-y-6 rounded-xl border bg-background p-8 shadow-lg">
          <div className="text-center">
            <Shield className="mx-auto h-10 w-10 text-primary mb-2" />
            <h1 className="text-xl font-bold">Admin Login</h1>
            <p className="text-sm text-muted-foreground mt-1">Enter admin password to continue.</p>
          </div>
          <Input
            type="password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setError(''); }}
            onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            placeholder="Admin password"
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button className="w-full" onClick={handleLogin}>Enter</Button>
        </div>
      </div>
    );
  }

  // Authenticated
  return (
    <>
      {/* Logout button in top-right corner */}
      <div className="fixed top-2 right-4 z-50">
        <Button variant="ghost" size="sm" className="text-xs text-muted-foreground" onClick={handleLogout}>
          Logout
        </Button>
      </div>
      {children}
    </>
  );
}
