'use client';

import { useUiStore } from '@/stores/ui-store';
import { useLanguageStore } from '@/stores/language-store';
import { useChatStore } from '@/stores/chat-store';
import { CITIZEN_LANGUAGES } from '@/lib/i18n/translations';
import { Menu, Sprout, Globe } from 'lucide-react';

export function MobileHeader() {
  const { openMobileSidebar } = useUiStore();
  const { currentLanguage, setLanguage, getCurrentLanguageObj } = useLanguageStore();
  const requestLanguageTransform = useChatStore((s) => s.requestLanguageTransform);
  const currentLang = getCurrentLanguageObj();

  const handleNextLanguage = () => {
    const currentIndex = CITIZEN_LANGUAGES.findIndex((l) => l.code === currentLanguage);
    const nextIndex = (currentIndex + 1) % CITIZEN_LANGUAGES.length;
    const nextCode = CITIZEN_LANGUAGES[nextIndex].code;
    setLanguage(nextCode);
    requestLanguageTransform(nextCode);
  };

  return (
    <header className="flex justify-between items-center w-full px-margin-mobile py-3.5 z-40 md:hidden bg-surface/95 backdrop-blur-md shadow-sm border-b border-surface-variant/40 shrink-0">
      <button
        type="button"
        onClick={openMobileSidebar}
        className="w-10 h-10 flex items-center justify-center rounded-full hover:bg-surface-variant text-on-surface-variant transition-colors active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
        aria-label="Open navigation drawer"
      >
        <Menu className="w-6 h-6 text-primary" />
      </button>

      <div className="flex items-center gap-2">
        <Sprout className="w-6 h-6 text-secondary" />
        <h1 className="text-xl font-bold text-primary tracking-tight">GramSakhi</h1>
      </div>

      {/* Language Quick Toggle */}
      <button
        type="button"
        onClick={handleNextLanguage}
        aria-label={`Change language, current language ${currentLang.englishName}`}
        className="h-8 px-3 flex items-center gap-1.5 rounded-full border border-outline-variant bg-surface-container-low text-on-surface font-semibold text-xs hover:bg-surface-variant transition-colors shadow-sm active:scale-95 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
      >
        <Globe className="w-3.5 h-3.5 text-secondary" />
        <span>{currentLang.name}</span>
      </button>
    </header>
  );
}
