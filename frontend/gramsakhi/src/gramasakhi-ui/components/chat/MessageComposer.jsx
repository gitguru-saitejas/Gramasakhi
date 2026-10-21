'use client';

import { useState, useRef, useEffect } from 'react';
import { useChatStore } from '@/stores/chat-store';
import { useLanguageStore } from '@/stores/language-store';
import { useVoice } from '@/lib/hooks/use-voice';
import { Mic, Send, Loader2 } from 'lucide-react';

export function MessageComposer() {
  const [inputText, setInputText] = useState('');
  const textareaRef = useRef(null);

  const { sendMessage, isGenerating } = useChatStore();
  const { currentLanguage, getTranslation } = useLanguageStore();
  const t = getTranslation();

  const { isListening, isProcessing, toggleListening, error: voiceError } = useVoice();

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [inputText]);

  const handleSend = () => {
    if (!inputText.trim() || isGenerating || isListening || isProcessing) return;
    sendMessage(inputText.trim(), currentLanguage);
    setInputText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = '44px';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleVoiceResult = (spokenText, voiceOpts) => {
    if (!spokenText?.trim() || isGenerating) return;
    sendMessage(spokenText.trim(), currentLanguage, voiceOpts || { input_mode: 'voice' });
    setInputText('');
  };

  const micBusy = isListening || isProcessing;
  const composerDisabled = isGenerating || micBusy;

  return (
    <div className="absolute bottom-16 md:bottom-0 left-0 right-0 p-3 md:p-5 bg-gradient-to-t from-surface via-surface/95 to-transparent z-30 pb-safe md:pb-6">
      <div className="max-w-[840px] mx-auto relative">
        <div className="bg-surface-container-high rounded-[32px] p-1.5 md:p-2 flex items-center gap-1.5 md:gap-2 shadow-ambient border border-surface-variant focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20 transition-all bg-opacity-95 backdrop-blur-sm">
          <textarea
            ref={textareaRef}
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isProcessing ? 'Processing voice…' : isListening ? t.listening : t.askPlaceholder
            }
            aria-label={t.askPlaceholder}
            rows={1}
            disabled={composerDisabled}
            className="flex-1 bg-transparent border-none focus:ring-0 resize-none font-sans text-sm md:text-base text-on-surface placeholder:text-outline-variant py-2.5 px-3 custom-scrollbar outline-none leading-normal disabled:opacity-60"
            style={{ minHeight: '44px', maxHeight: '120px' }}
          />

          <div className="flex items-center gap-1 shrink-0 pr-1">
            <button
              type="button"
              onClick={() => toggleListening(handleVoiceResult)}
              disabled={isGenerating || isProcessing}
              title="Voice input"
              className={`p-2.5 md:p-3 rounded-full transition-all active:scale-95 relative ${
                isListening
                  ? 'bg-error-container text-on-error-container animate-pulse ring-2 ring-error'
                  : 'text-on-surface-variant hover:text-primary hover:bg-surface-variant'
              } disabled:opacity-50`}
              aria-label={isListening ? 'Stop recording' : 'Voice input'}
              aria-pressed={isListening}
            >
              {isProcessing ? (
                <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
              ) : (
                <Mic className="w-5 h-5" />
              )}
            </button>

            <button
              type="button"
              onClick={handleSend}
              disabled={!inputText.trim() || composerDisabled}
              title="Send Message"
              className="p-2.5 md:p-3 bg-primary text-on-primary rounded-full hover:bg-surface-tint transition-all active:scale-90 flex items-center justify-center shadow-ambient disabled:opacity-50 disabled:cursor-not-allowed"
              aria-label="Send Message"
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
        </div>

        {voiceError && (
          <p className="text-center mt-2 text-xs text-error font-medium" role="alert">
            {voiceError}
          </p>
        )}

        <div className="text-center mt-1.5">
          <p className="text-[10px] text-outline">{t.disclaimer}</p>
        </div>
      </div>
    </div>
  );
}
