/**
 * Projects page — placeholder. Will list user's project folders,
 * each containing grouped conversations on a specific topic.
 */

'use client';

import { useRouter } from 'next/navigation';
import { useLocale } from 'next-intl';
import { Button } from '@/components/ui/button';
import { Folder, ArrowLeft } from 'lucide-react';

const MOCK_PROJECTS = [
  { id: '1', name: 'LNG Carrier Design', conversations: 8 },
  { id: '2', name: 'Ballast Water Compliance', conversations: 5 },
  { id: '3', name: 'Bulk Carrier Hatch Study', conversations: 12 },
  { id: '4', name: 'Offshore Wind Platform', conversations: 3 },
];

export default function ProjectsPage() {
  const router = useRouter();
  const locale = useLocale();

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <button
        onClick={() => router.push(`/${locale}/chat`)}
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground mb-6"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to chat
      </button>

      <h1 className="text-xl font-bold mb-2">Projects</h1>
      <p className="text-sm text-muted-foreground mb-6">
        Organize your conversations by topic or project.
      </p>

      <div className="space-y-2">
        {MOCK_PROJECTS.map((p) => (
          <div
            key={p.id}
            className="flex items-center gap-3 rounded-lg border p-4 hover:bg-muted/30 cursor-pointer transition-colors"
          >
            <Folder className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">{p.name}</p>
              <p className="text-xs text-muted-foreground">{p.conversations} conversations</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
