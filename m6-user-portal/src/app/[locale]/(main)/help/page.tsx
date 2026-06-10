/**
 * Help & Documentation page.
 */
'use client';

import { useTranslations } from 'next-intl';

export default function HelpPage() {
  return (
    <div className="mx-auto max-w-3xl overflow-y-auto p-8">
      <h1 className="text-2xl font-bold mb-2">Help & Documentation</h1>
      <p className="text-sm text-muted-foreground mb-8">
        Learn how to use the Marine & Offshore Expert System effectively.
      </p>

      <div className="space-y-8">
        <Section title="Getting Started"
          content="Type your engineering question in the chat input and press Enter. The system searches maritime regulations, classification society rules (DNV, ABS, CCS, LR, BV), and engineering knowledge to provide citation-backed answers." />

        <Section title="Asking Good Questions"
          content="Include specific clause references (e.g., 'DNV Pt.4 Ch.3 §5') for precise results. Mention the vessel type, steel grade, or system for domain-specific answers. For comparisons, ask 'Compare DNV and ABS requirements for...'" />

        <Section title="Uploading Documents"
          content="Drag & drop PDF, DOCX, XLSX, or image files anywhere on the page, or click the 📎 button. The system parses the document and uses its content to answer your questions. Supported formats: PDF, DOCX, XLSX, PPTX, HTML, TXT, MD, CSV, PNG, JPG, TIFF." />

        <Section title="Web Search"
          content="Toggle the 🌐 button to include live web search results in your answers. Useful for recent regulatory updates or manufacturer specifications not yet in the knowledge base. Web search is enabled per-message — toggle it on/off anytime." />

        <Section title="Citations"
          content="Every answer includes numbered citations in the right panel. Click a citation number to see the exact source: classification society, regulation chapter, section, and the relevant text excerpt. Citations let you verify answers against the original documents." />

        <Section title="Conversations"
          content="Your chat history is saved automatically in the sidebar. Right-click any conversation to rename, share, pin, or delete it. Use the search bar (🔍) to find past conversations by keyword." />

        <Section title="Settings & Account"
          content="Click ⚙ Settings in the sidebar to change language, theme, or manage your profile. You can upload an avatar, and delete your account from the Profile tab. Language changes take effect immediately without reloading." />

        <Section title="API Access"
          content="Developers can access the system programmatically via the OpenAI-compatible API at /v1/chat/completions. Generate an API key from the Admin Portal (M7) → API Keys. Use the key as a Bearer token: Authorization: Bearer sk-m8-xxxx. Full API documentation is available in the project README." />

        <div className="rounded-lg border bg-muted/30 p-4">
          <p className="text-sm font-medium mb-2">Need more help?</p>
          <p className="text-xs text-muted-foreground">
            This is the Marine & Offshore Expert System. For bug reports, feature requests,
            or enterprise support, contact the development team or check the project repository.
          </p>
        </div>
      </div>
    </div>
  );
}

function Section({ title, content }: { title: string; content: string }) {
  return (
    <div>
      <h2 className="text-base font-semibold mb-1">{title}</h2>
      <p className="text-sm text-muted-foreground leading-relaxed">{content}</p>
    </div>
  );
}
