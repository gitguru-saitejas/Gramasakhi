'use client';

import { useEffect, useRef, useState } from 'react';
import { useLanguageStore } from '@/stores/language-store';
import { useChatStore } from '@/stores/chat-store';
import { CITIZEN_LANGUAGES } from '@/lib/i18n/translations';
import { Globe, Volume2, VolumeX, RotateCcw, ChevronDown, Check } from 'lucide-react';

export function ChatHeader() {
  const { currentLanguage, setLanguage, isTtsEnabled, toggleTts, getCurrentLanguageObj, getTranslation } = useLanguageStore();
  const { clearChat, requestLanguageTransform } = useChatStore();
  const t = getTranslation();
  const currentLangObj = getCurrentLanguageObj();
  const [langOpen, setLangOpen] = useState(false);
  const langMenuRef = useRef(null);

  useEffect(() => {
    if (!langOpen) return;
    const onPointerDown = (event) => {
      if (!langMenuRef.current?.contains(event.target)) {
        setLangOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [langOpen]);

  return (
    <header className="h-16 border-b border-surface-variant/70 bg-surface/90 backdrop-blur-md items-center justify-between px-6 sticky top-0 z-40 hidden md:flex shrink-0">
      {/* Title & Status */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="text-base font-bold text-primary">GramSakhi Advisor</span>
          <span className="px-2.5 py-0.5 rounded-full bg-secondary-container text-on-secondary-container text-xs font-semibold flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-secondary animate-pulse" />
            {t.activeStatus}
          </span>
        </div>
        <span className="text-xs text-on-surface-variant bg-surface-container-high px-2.5 py-0.5 rounded-full font-medium">
          Gov Scheme Grounded RAG
        </span>
      </div>

      {/* Action Controls */}
      <div className="flex items-center gap-3">
        {/* Multilingual Selector */}
        <div className="relative" ref={langMenuRef}>
          <button
            type="button"
            onClick={() => setLangOpen((open) => !open)}
            aria-haspopup="listbox"
            aria-expanded={langOpen}
            aria-label="Select language"
            className="flex items-center gap-1.5 text-xs font-semibold text-primary bg-surface-container px-3 py-1.5 rounded-full border border-surface-variant hover:bg-surface-container-high transition-colors shadow-sm focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          >
            <Globe className="w-3.5 h-3.5 text-secondary" />
            <span>{currentLangObj.name} ({currentLangObj.englishName})</span>
            <ChevronDown className="w-3.5 h-3.5" />
          </button>

          {langOpen && (
            <div
              role="listbox"
              aria-label="Languages"
              className="absolute right-0 mt-1 w-48 bg-surface-container-lowest rounded-2xl shadow-xl border border-surface-variant p-1.5 z-50 space-y-0.5"
            >
              {CITIZEN_LANGUAGES.map((lang) => (
                <button
                  key={lang.code}
                  type="button"
                  role="option"
                  aria-selected={currentLanguage === lang.code}
                  onClick={() => {
                    if (lang.code !== currentLanguage) {
                      setLanguage(lang.code);
                      requestLanguageTransform(lang.code);
                    }
                    setLangOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2 text-xs rounded-xl transition-colors font-medium flex items-center justify-between ${
                    currentLanguage === lang.code
                      ? 'bg-secondary-container text-primary font-bold'
                      : 'hover:bg-surface-container text-on-surface'
                  }`}
                >
                  <span>{lang.name} ({lang.englishName})</span>
                  {currentLanguage === lang.code && <Check className="w-3.5 h-3.5 text-secondary" />}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Text-to-Speech Audio Readout Toggle */}
        <button
          type="button"
          onClick={toggleTts}
          title={isTtsEnabled ? 'Disable Voice Readout' : 'Enable Voice Readout'}
          className={`w-9 h-9 rounded-full border flex items-center justify-center transition-colors active:scale-95 shadow-sm ${
            isTtsEnabled
              ? 'bg-secondary-container border-secondary text-primary'
              : 'bg-surface-container border-surface-variant text-on-surface-variant hover:bg-surface-container-high'
          }`}
          aria-label="Voice Readout Toggle"
        >
          {isTtsEnabled ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
        </button>

        {/* Reset Chat */}
        <button
          type="button"
          onClick={clearChat}
          title="Reset Consultation"
          className="w-9 h-9 rounded-full bg-surface-container hover:bg-surface-container-high border border-surface-variant flex items-center justify-center text-on-surface-variant hover:text-error transition-colors active:scale-95 shadow-sm"
          aria-label="Reset Chat"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
