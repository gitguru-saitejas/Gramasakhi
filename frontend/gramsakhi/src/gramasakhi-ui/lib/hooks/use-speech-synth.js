'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import { useLanguageStore } from '@/stores/language-store';
import { synthesizeSpeech } from '@/lib/api/chat-api';
import { uiLangToApi } from '@/lib/api/backend-adapter';

function stripMarkdownForSpeech(text) {
  return (text || '')
    .replace(/[#*_`~[\]()]/g, '')
    .replace(/- /g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/**
 * Backend edge-tts playback (KN/HI/EN) — same path as Android TtsPlaybackContext.
 */
export function useSpeechSynth() {
  const [phase, setPhase] = useState('idle'); // idle | loading | playing
  const [error, setError] = useState(null);
  const audioRef = useRef(null);
  const objectUrlRef = useRef(null);
  const { isTtsEnabled, currentLanguage } = useLanguageStore();

  const cleanupAudio = useCallback(() => {
    if (audioRef.current) {
      try {
        audioRef.current.pause();
        audioRef.current.src = '';
      } catch {
        // ignore
      }
      audioRef.current = null;
    }
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
  }, []);

  useEffect(() => {
    return () => cleanupAudio();
  }, [cleanupAudio]);

  const stop = useCallback(() => {
    cleanupAudio();
    setPhase('idle');
  }, [cleanupAudio]);

  const speak = useCallback(async (text) => {
    if (!isTtsEnabled) return;
    const cleanText = stripMarkdownForSpeech(text);
    if (!cleanText) return;

    stop();
    setError(null);
    setPhase('loading');

    try {
      const blob = await synthesizeSpeech(cleanText, {
        language: currentLanguage,
      });
      if (!blob || blob.size === 0) {
        throw new Error('empty_audio');
      }
      const url = URL.createObjectURL(blob);
      objectUrlRef.current = url;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        stop();
      };
      audio.onerror = () => {
        setError('Voice playback is not available right now.');
        stop();
      };
      await audio.play();
      setPhase('playing');
    } catch {
      setError('Voice playback is not available right now.');
      stop();
    }
  }, [isTtsEnabled, currentLanguage, stop]);

  return {
    isSpeaking: phase === 'playing',
    isLoading: phase === 'loading',
    error,
    speak,
    stop,
    ttsLanguage: uiLangToApi(currentLanguage),
  };
}
