'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Bot, Sparkles } from 'lucide-react';
import { SchemeCard } from '@/components/schemes/SchemeCard';
import { SourceList } from '@/components/evidence/SourceList';
import { ListenButton } from '@/components/chat/ListenButton';
import { SufficiencyBadge } from '@/components/evidence/SufficiencyBadge';
import { EligibilityGuidancePanel } from './EligibilityGuidancePanel';
import { safeMarkdownUrl } from '@/lib/utils';

export function AssistantMessage({ message }) {
  const groundingState = message.grounding?.sufficiency || 'SUPPORTED';

  return (
    <div className="flex items-start gap-3 md:gap-4 mb-6">
      {/* Bot Avatar Icon matching Stitch design */}
      <div className="w-10 h-10 rounded-full bg-primary-container text-on-primary-container flex-shrink-0 flex items-center justify-center mt-1 shadow-sm ring-1 ring-secondary-container">
        <Bot className="w-5 h-5 text-tertiary-fixed-dim" />
      </div>

      <div className="flex-1 space-y-3 max-w-[92%] md:max-w-[85%]">
        {/* Verification Status Badge */}
        {message.grounding && (
          <div className="flex items-center gap-2 mb-1">
            <SufficiencyBadge state={groundingState} />
            {message.grounding.verificationNote && (
              <span className="text-[11px] text-on-surface-variant hidden sm:inline-block">
                • {message.grounding.verificationNote}
              </span>
            )}
          </div>
        )}

        {/* Markdown Content Area */}
        <div className="bg-surface-container-low md:bg-transparent p-4 md:p-0 rounded-2xl shadow-ambient md:shadow-none border md:border-none border-surface-variant/50">
          <ListenButton
            text={message.content}
            messageId={message.id}
            language={message.language}
            className="mb-2"
          />
          <div className="prose prose-sm md:prose-base max-w-none text-on-surface leading-relaxed space-y-2 prose-headings:font-bold prose-headings:text-primary prose-strong:text-primary prose-a:text-secondary prose-ul:my-2 prose-li:my-0.5">
            <ReactMarkdown remarkPlugins={[remarkGfm]} urlTransform={safeMarkdownUrl}>
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Scheme Cards */}
          {message.schemes && message.schemes.length > 0 && (
            <div className="space-y-3 mt-4">
              {message.schemes.map((scheme) => (
                <SchemeCard key={scheme.id} scheme={scheme} />
              ))}
            </div>
          )}

          {/* Evidence / Source List */}
          {message.sources && message.sources.length > 0 && (
            <SourceList sources={message.sources} />
          )}

          <EligibilityGuidancePanel meta={message.meta} />
        </div>
      </div>
    </div>
  );
}
