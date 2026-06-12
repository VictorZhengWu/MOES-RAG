/** Notification bell with unread badge and dropdown (00110-08/4-D). */
'use client';

import { useState, useEffect } from 'react';
import { Bell } from 'lucide-react';

export function NotificationBell({ token }: { token: string }) {
  const [notifications, setNotifications] = useState<any[]>([]);
  const [show, setShow] = useState(false);
  const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
  const unread = notifications.filter((n: any) => !n.is_read).length;

  useEffect(() => {
    const h: any = { Authorization: `Bearer ${token}` };
    const fetchN = () => fetch(`${BASE_URL}/api/v1/projects/notifications`, { headers: h })
      .then(r => r.json()).then(setNotifications).catch(() => {});
    fetchN();
    const interval = setInterval(fetchN, 30000);
    return () => clearInterval(interval);
  }, [token]);

  return (
    <div className="relative inline-flex">
      <button className="relative p-1 rounded hover:bg-muted" onClick={() => setShow(!show)}>
        <Bell className="h-4 w-4" />
        {unread > 0 && (
          <span className="absolute -top-0.5 -right-0.5 bg-red-500 text-white rounded-full w-4 h-4 text-[10px] flex items-center justify-center font-bold">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>
      {show && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setShow(false)} />
          <div className="absolute right-0 top-full mt-1 w-64 bg-background border rounded-lg shadow-lg z-50 max-h-64 overflow-y-auto">
            <p className="text-xs font-medium px-3 py-2 border-b">Notifications</p>
            {notifications.slice(0, 10).map((n: any) => (
              <div key={n.notification_id}
                className={`px-3 py-2 text-xs border-b last:border-0 ${!n.is_read ? 'bg-muted/50 font-medium' : ''} hover:bg-muted cursor-pointer`}>
                <p>{n.title}</p>
                <p className="text-[10px] text-muted-foreground">
                  {new Date(n.created_at * 1000).toLocaleString()}
                </p>
              </div>
            ))}
            {notifications.length === 0 && (
              <p className="text-xs text-muted-foreground px-3 py-4 text-center">No notifications</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
