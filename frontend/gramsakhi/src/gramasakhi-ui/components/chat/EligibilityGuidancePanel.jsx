'use client';

import { ExternalLink, FileText, HelpCircle, Landmark, ListChecks, Route } from 'lucide-react';
import { useLanguageStore } from '@/stores/language-store';
import { safeHttpUrl } from '@/lib/utils';

function statusTone(status) {
  const raw = (status || '').trim();
  const s = raw.toLowerCase().replace(/-/g, '_');
  const upper = raw.toUpperCase();
  if (s === 'eligible' || upper === 'ELIGIBLE') {
    return 'bg-secondary-container text-on-secondary-container';
  }
  if (s === 'ineligible' || s === 'not_eligible' || upper === 'NOT_ELIGIBLE') {
    return 'bg-error-container text-on-error-container';
  }
  if (s === 'uncertain' || s === 'cannot_determine' || upper === 'CANNOT_DETERMINE') {
    return 'bg-surface-container-high text-on-surface-variant';
  }
  return 'bg-surface-container text-on-surface-variant';
}

const QUESTION_LABELS = {
  age: { en: 'Your age', kn: 'ನಿಮ್ಮ ವಯಸ್ಸು', hi: 'आपकी उम्र' },
  state: { en: 'Your state', kn: 'ನಿಮ್ಮ ರಾಜ್ಯ', hi: 'आपका राज्य' },
  income: { en: 'Your income', kn: 'ನಿಮ್ಮ ಆದಾಯ', hi: 'आपकी आय' },
  gender: { en: 'Your gender', kn: 'ಲಿಂಗ', hi: 'लिंग' },
  occupation: { en: 'Your occupation', kn: 'ವೃತ್ತಿ', hi: 'व्यवसाय' },
};

export function EligibilityGuidancePanel({ meta }) {
  const { currentLanguage } = useLanguageStore();
  const lang = currentLanguage || 'en';
  if (!meta) return null;

  const guidance = meta.scheme_guidance;
  const plan = meta.action_plan;
  const docs = guidance?.documents || plan?.documents || [];
  const steps =
    guidance?.application_steps ||
    (Array.isArray(plan?.steps) ? plan.steps.map((s) => (typeof s === 'string' ? s : s?.text)).filter(Boolean) : []);
  const guidanceSources = (guidance?.source_urls || plan?.source_urls || []).filter((s) => {
    const url = s?.url || s?.source || s?.document_url;
    return Boolean(safeHttpUrl(url));
  });

  const applicationUrl = safeHttpUrl(plan?.application_url);
  const guidanceApplicationUrl = safeHttpUrl(guidance?.application_url) || applicationUrl;
  const pdfUrls = (plan?.pdf_urls || []).map((url) => safeHttpUrl(url)).filter(Boolean);

  const qLabel = (type) =>
    QUESTION_LABELS[type]?.[lang] || QUESTION_LABELS[type]?.en || type;

  return (
    <div className="mt-4 pt-3 border-t border-surface-variant/70 space-y-2">
      {meta.detected_scheme && (
        <p className="text-xs font-semibold text-primary flex items-center gap-1.5">
          <Landmark className="w-3.5 h-3.5 text-secondary" />
          {meta.detected_scheme}
        </p>
      )}

      {meta.eligibility_status && (
        <span className={`inline-flex text-[11px] font-bold px-2.5 py-1 rounded-full ${statusTone(meta.eligibility_status)}`}>
          {meta.eligibility_status.replace(/_/g, ' ')}
        </span>
      )}

      {meta.eligibility_session_active && meta.eligibility_question && (
        <p className="text-xs text-on-surface-variant flex items-center gap-1">
          <HelpCircle className="w-3.5 h-3.5" />
          {qLabel(meta.eligibility_question)}
        </p>
      )}

      {Array.isArray(meta.missing_information) && meta.missing_information.length > 0 && (
        <p className="text-xs text-on-surface-variant">
          Still needed: {meta.missing_information.join(', ')}
        </p>
      )}

      {(plan?.steps?.length > 0 || plan?.next_step) && (
        <div className="rounded-2xl bg-surface-container-low border border-secondary/30 p-3 space-y-2">
          <p className="text-[11px] font-bold text-secondary uppercase flex items-center gap-1">
            <Route className="w-3 h-3" />
            {lang === 'kn' ? 'ಮುಂದಿನ ಹಂತಗಳು' : lang === 'hi' ? 'अगले कदम' : 'Next steps'}
          </p>
          {plan.next_step && (
            <p className="text-xs text-on-surface font-medium">{plan.next_step}</p>
          )}
          {Array.isArray(plan.steps) && plan.steps.length > 0 && (
            <ol className="list-decimal list-inside text-xs text-on-surface space-y-0.5">
              {plan.steps.slice(0, 6).map((s, i) => {
                const text = typeof s === 'string' ? s : s?.text;
                if (!text) return null;
                return <li key={`${i}-${text.slice(0, 24)}`}>{text}</li>;
              })}
            </ol>
          )}
          {applicationUrl && (
            <a
              href={applicationUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-secondary hover:underline"
            >
              Application portal
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
          {pdfUrls.map((url) => (
            <a
              key={url}
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs font-semibold text-secondary hover:underline"
            >
              Official scheme document (PDF)
              <ExternalLink className="w-3 h-3 shrink-0" />
            </a>
          ))}
        </div>
      )}

      {(docs.length > 0 || steps.length > 0 || guidanceApplicationUrl || guidanceSources.length > 0) && (
        <div className="rounded-2xl bg-surface-container-low border border-surface-variant/60 p-3 space-y-2">
          {guidanceApplicationUrl && (
            <a
              href={guidanceApplicationUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-secondary hover:underline"
            >
              Application portal
              <ExternalLink className="w-3.5 h-3.5" />
            </a>
          )}
          {docs.length > 0 && (
            <div>
              <p className="text-[11px] font-bold text-on-surface-variant uppercase flex items-center gap-1">
                <FileText className="w-3 h-3" /> Documents
              </p>
              <ul className="list-disc list-inside text-xs text-on-surface mt-1">
                {docs.slice(0, 6).map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
            </div>
          )}
          {steps.length > 0 && (
            <div>
              <p className="text-[11px] font-bold text-on-surface-variant uppercase flex items-center gap-1">
                <ListChecks className="w-3 h-3" /> Application steps
              </p>
              <ol className="list-decimal list-inside text-xs text-on-surface mt-1">
                {steps.slice(0, 5).map((s) => (
                  <li key={s}>{s}</li>
                ))}
              </ol>
            </div>
          )}
          {guidanceSources.map((s) => {
            const url = safeHttpUrl(s.url || s.source || s.document_url);
            if (!url) return null;
            const isPdf = Boolean(s.is_pdf) || /\.pdf(\?|$)/i.test(url);
            return (
              <a
                key={url}
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 text-xs font-semibold text-secondary hover:underline"
              >
                {isPdf ? 'Official scheme document (PDF)' : url}
                <ExternalLink className="w-3 h-3 shrink-0" />
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
