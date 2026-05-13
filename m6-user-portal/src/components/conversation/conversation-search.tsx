/**
 * Conversation search with client-side filtering.
 *
 * WHY: The mock API returns all conversations at once. Client-side
 * search is fast for < 100 items and gives instant results without
 * network round-trips. When M5 adds server-side search, this
 * component will be adapted to debounce API calls.
 */

'use client';

import { useState } from 'react';
import { useTranslations } from 'next-intl';
import { Input } from '@/components/ui/input';
import { SearchIcon } from 'lucide-react';

interface Props {
  onSearch?: (query: string) => void;
}

export function ConversationSearch({ onSearch }: Props) {
  const t = useTranslations();
  const [query, setQuery] = useState('');

  const handleChange = (value: string) => {
    setQuery(value);
    onSearch?.(value);
  };

  return (
    <div className="relative">
      <SearchIcon className="absolute left-2 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
      <Input
        value={query}
        onChange={(e) => handleChange(e.target.value)}
        placeholder={t('conversation.search')}
        className="h-8 pl-8 text-xs"
      />
    </div>
  );
}
