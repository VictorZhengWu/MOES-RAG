/**
 * Help & Documentation page — all text externalized via i18n.
 */
'use client';

import { useTranslations } from 'next-intl';

export default function HelpPage() {
  const t = useTranslations();

  return (
    <div className="mx-auto max-w-3xl overflow-y-auto p-8">
      <h1 className="text-2xl font-bold mb-2">{t('help.title')}</h1>
      <p className="text-sm text-muted-foreground mb-8">{t('help.subtitle')}</p>

      <div className="space-y-8">
        <Section title={t('help.gettingStarted.title')} content={t('help.gettingStarted.body')} />
        <Section title={t('help.askingQuestions.title')} content={t('help.askingQuestions.body')} />
        <Section title={t('help.uploading.title')} content={t('help.uploading.body')} />
        <Section title={t('help.webSearch.title')} content={t('help.webSearch.body')} />
        <Section title={t('help.citations.title')} content={t('help.citations.body')} />
        <Section title={t('help.conversations.title')} content={t('help.conversations.body')} />
        <Section title={t('help.settings.title')} content={t('help.settings.body')} />
        <Section title={t('help.apiAccess.title')} content={t('help.apiAccess.body')} />

        <div className="rounded-lg border bg-muted/30 p-4">
          <p className="text-sm font-medium mb-2">{t('help.moreHelp.title')}</p>
          <p className="text-xs text-muted-foreground">{t('help.moreHelp.body')}</p>
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
