'use client';



import { Volume2 } from 'lucide-react';

import { useLanguageStore } from '@/stores/language-store';

import { useMessageTts } from '@/context/TtsPlaybackContext';



export function ListenButton({ text, messageId, language, className = '' }) {

  const { getTranslation, currentLanguage } = useLanguageStore();

  const t = getTranslation();

  const ttsLanguage = language || currentLanguage;

  const { speak, stop, isSpeaking, isLoading, error } = useMessageTts(

    messageId || `listen-${(text || '').slice(0, 32)}`,

    ttsLanguage

  );

  const clean = (text || '').trim();



  if (!clean) return null;



  return (

    <div className={className}>

      <button

        type="button"

        onClick={() => (isSpeaking || isLoading ? stop() : speak(clean))}

        disabled={isLoading}

        className="flex items-center gap-1.5 px-2.5 py-1 text-xs text-secondary hover:bg-secondary-container/50 rounded-md transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 disabled:opacity-60"

        aria-label={isSpeaking ? t.stopAudio : t.listenAudio}

        aria-busy={isLoading}

      >

        <Volume2 className={`w-3.5 h-3.5 ${isSpeaking ? 'animate-pulse text-error' : ''}`} />

        <span>{isLoading ? '…' : isSpeaking ? t.stopAudio : t.listenAudio}</span>

      </button>

      {error ? (

        <p className="text-[10px] text-error mt-1" role="alert">

          {error}

        </p>

      ) : null}

    </div>

  );

}

