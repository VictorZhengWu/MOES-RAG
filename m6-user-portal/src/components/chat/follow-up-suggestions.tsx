/**
 * Follow-up question suggestions shown after an AI response.
 * Phase 1: mock suggestions based on keywords. Phase 2: LLM-generated.
 */

'use client';

import { Button } from '@/components/ui/button';
import { Sparkles } from 'lucide-react';

// Mock suggestions based on the conversation content
const MOCK_FOLLOW_UPS = [
  'Can you provide more details about the structural requirements?',
  'How does this compare to ABS equivalent rules?',
  'What are the material specifications for this?',
];

interface Props {
  onSelect: (question: string) => void;
}

export function FollowUpSuggestions({ onSelect }: Props) {
  return (
    <div className="px-4 py-2" style={{ paddingLeft: '10%' }}>
      <div className="flex items-center gap-1.5 mb-2">
        <Sparkles className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">Suggested follow-ups</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {MOCK_FOLLOW_UPS.map((q, i) => (
          <Button
            key={i}
            variant="outline"
            size="sm"
            className="text-xs h-7 rounded-full"
            onClick={() => onSelect(q)}
          >
            {q}
          </Button>
        ))}
      </div>
    </div>
  );
}
