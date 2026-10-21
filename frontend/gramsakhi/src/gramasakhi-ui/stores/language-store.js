import { create } from 'zustand';
import { CITIZEN_LANGUAGES, LANGUAGES, TRANSLATIONS } from '@/lib/i18n/translations';

export const useLanguageStore = create((set, get) => ({
  currentLanguage: 'kn', // default to Kannada as in Stitch reference
  isTtsEnabled: true,

  setLanguage: (langCode) => {
    const allowed = CITIZEN_LANGUAGES.some((l) => l.code === langCode);
    if (allowed) {
      set({ currentLanguage: langCode });
      if (typeof window !== 'undefined') {
        localStorage.setItem('gramsakhi_lang', langCode);
      }
    }
  },

  toggleTts: () => {
    set((state) => ({ isTtsEnabled: !state.isTtsEnabled }));
  },

  getTranslation: () => {
    const lang = get().currentLanguage;
    return TRANSLATIONS[lang] || TRANSLATIONS.en;
  },

  getCurrentLanguageObj: () => {
    const lang = get().currentLanguage;
    return LANGUAGES.find((l) => l.code === lang) || LANGUAGES[0];
  },

  initLanguageFromStorage: () => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('gramsakhi_lang');
      if (saved && CITIZEN_LANGUAGES.some((l) => l.code === saved)) {
        set({ currentLanguage: saved });
      }
    }
  }
}));
