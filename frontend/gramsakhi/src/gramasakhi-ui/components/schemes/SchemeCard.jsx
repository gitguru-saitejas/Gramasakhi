'use client';

import { useState } from 'react';
import { useChatStore } from '@/stores/chat-store';
import { useLanguageStore } from '@/stores/language-store';
import { openExternalApplyUrl, resolveSchemeApplyTarget } from '@/lib/scheme-apply';
import { Sprout, ChevronRight, ExternalLink } from 'lucide-react';

/** Displays backend-detected scheme name only — no hard-coded catalogue. */
export function SchemeCard({ scheme, meta, raw, sources }) {
  const { sendMessage } = useChatStore();
  const { currentLanguage, getTranslation } = useLanguageStore();
  const t = getTranslation();
  const [applyNotice, setApplyNotice] = useState(null);

  if (!scheme?.name) return null;

  const applyTarget = resolveSchemeApplyTarget({ scheme, meta, raw, sources });

  const askHowToApply = () => {
    const prompts = {
      en: `How do I apply for ${scheme.name}?`,
      kn: `${scheme.name} ಗೆ ಅರ್ಜಿ ಸಲ್ಲಿಸುವ ವಿಧಾನ ಏನು?`,
      hi: `${scheme.name} के लिए आवेदन कैसे करें?`,
    };
    sendMessage(prompts[currentLanguage] || prompts.en, currentLanguage);
  };

  const handleApplyOnline = () => {
    if (applyTarget?.url) {
      const opened = openExternalApplyUrl(applyTarget.url);
      if (!opened) {
        setApplyNotice(
          t.applyLinkBlocked ||
            'This link could not be opened safely. Use the official sources below.'
        );
      }
      return;
    }
    setApplyNotice(
      t.noVerifiedApplyUrl ||
        'No verified online application link is available yet. You can ask how to apply in chat.'
    );
  };

  const applyLabel =
    applyTarget?.kind === 'application'
      ? t.applyNow || 'Apply Online'
      : applyTarget?.kind === 'official_information'
        ? t.openOfficialSchemePage || 'Open Official Scheme Page'
        : t.applyNow || 'Apply Online';

  return (
    <div className="bg-surface-container rounded-[28px] p-5 shadow-ambient border border-surface-variant max-w-md w-full mt-4">
      <div className="flex items-start justify-between mb-3">
        <div>
          <span className="inline-block px-3 py-1 bg-tertiary-fixed-dim text-on-tertiary-fixed font-semibold text-xs rounded-full mb-2">
            Detected scheme
          </span>
          <h3 className="text-lg font-bold text-primary tracking-tight">{scheme.name}</h3>
        </div>
        <div className="w-10 h-10 rounded-full bg-secondary-container flex items-center justify-center shrink-0">
          <Sprout className="w-6 h-6 text-secondary" />
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={handleApplyOnline}
          className="w-full bg-primary text-on-primary py-2.5 px-4 rounded-full font-bold text-xs hover:bg-surface-tint transition-all flex items-center justify-center gap-1"
        >
          <span>{applyLabel}</span>
          {applyTarget?.url ? (
            <ExternalLink className="w-3.5 h-3.5" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" />
          )}
        </button>
        <button
          type="button"
          onClick={askHowToApply}
          className="w-full bg-surface-container-high text-primary py-2 px-4 rounded-full font-semibold text-xs border border-surface-variant hover:bg-surface-variant transition-all"
        >
          {t.howToApplyInChat || 'How to Apply (in chat)'}
        </button>
      </div>

      {applyNotice && (
        <p className="text-[11px] text-on-surface-variant mt-2" role="status">
          {applyNotice}
        </p>
      )}
    </div>
  );
}
