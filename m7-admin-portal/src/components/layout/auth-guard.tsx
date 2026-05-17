/**
 * Auth Guard for M7 admin pages.
 * Phase 1: simple username+password lookup against mock database.
 * Phase 2: real JWT/OAuth admin authentication.
 */

'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Shield } from 'lucide-react';

const AUTH_KEY = 'm7-admin-auth';
const USER_KEY = 'm7-admin-user';

/**
 * Mock admin user database — configurable.
 * Phase 2: replace with API call to M5 Auth.
 */
const ADMIN_USERS: { username: string; password: string; role: string }[] = [
  { username: 'admin',  password: 'admin123',  role: 'admin' },
  { username: 'editor', password: 'editor123', role: 'editor' },
  { username: 'victor', password: 'victor123', role: 'admin' },
];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const [authed, setAuthed] = useState<boolean | null>(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [currentUser, setCurrentUser] = useState('');

  useEffect(() => {
    const stored = localStorage.getItem(AUTH_KEY);
    const user = localStorage.getItem(USER_KEY) || '';
    setAuthed(stored === 'true');
    setCurrentUser(user);
  }, []);

  const handleLogin = () => {
    const user = ADMIN_USERS.find(
      (u) => u.username === username && u.password === password,
    );
    if (user) {
      localStorage.setItem(AUTH_KEY, 'true');
      localStorage.setItem(USER_KEY, user.username);
      setAuthed(true);
      setCurrentUser(user.username);
      setError('');
    } else {
      setError('Invalid username or password.');
    }
  };

  const handleLogout = () => {
    localStorage.removeItem(AUTH_KEY);
    localStorage.removeItem(USER_KEY);
    setAuthed(false);
    setCurrentUser('');
    setUsername('');
    setPassword('');
  };

  if (authed === null) return null;

  if (!authed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-muted/20">
        <div className="w-full max-w-sm space-y-5 rounded-xl border bg-background p-8 shadow-lg">
          <div className="text-center">
            <Shield className="mx-auto h-10 w-10 text-primary mb-2" />
            <h1 className="text-xl font-bold">Admin Login</h1>
            <p className="text-sm text-muted-foreground mt-1">Sign in to access the admin panel.</p>
          </div>
          <Input
            value={username}
            onChange={(e) => { setUsername(e.target.value); setError(''); }}
            onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            placeholder="Username"
          />
          <Input
            type="password"
            value={password}
            onChange={(e) => { setPassword(e.target.value); setError(''); }}
            onKeyDown={(e) => e.key === 'Enter' && handleLogin()}
            placeholder="Password"
          />
          {error && <p className="text-sm text-destructive">{error}</p>}
          <Button className="w-full" onClick={handleLogin}>Sign In</Button>
        </div>
      </div>
    );
  }

  // Sidebar handles user display + logout
  return <>{children}</>;
}
