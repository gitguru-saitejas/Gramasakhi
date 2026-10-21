'use client';

import { useLanguageStore } from '@/stores/language-store';
import { ExternalLink, CheckCircle2 } from 'lucide-react';
import { safeHttpUrl } from '@/lib/utils';

export function SourceList({ sources = [] }) {
  const { getTranslation } = useLanguageStore();
  const t = getTranslation();

  if (!sources || sources.length === 0) return null;

  return (
    <div className="mt-4 pt-3 border-t border-surface-variant/70">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-bold text-on-surface-variant uppercase tracking-wider">
          {t.sources}
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {sources.filter((src) => src.url && src.url !== '#').map((src, idx) => {
          const href = safeHttpUrl(src.url);
          if (!href) return null;
          return (
          <a
            key={src.id || idx}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-surface rounded-lg border border-surface-variant text-xs text-on-surface shadow-ambient hover:bg-surface-container transition-colors max-w-full"
          >
            <CheckCircle2 className="w-3.5 h-3.5 text-secondary shrink-0" />
            <span className="truncate max-w-[200px]">{src.title || src.department || 'Official Gov Portal'}</span>
            <ExternalLink className="w-3 h-3 text-on-surface-variant shrink-0" />
          </a>
          );
        })}
      </div>
    </div>
  );
}
