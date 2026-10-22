'use client';

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useLanguageStore } from '@/stores/language-store';
import { synthesizeSpeech } from '@/lib/api/chat-api';
import { uiLangToApi } from '@/lib/api/backend-adapter';

const TtsPlaybackContext = createContext(null);

function stripMarkdownForSpeech(text) {
  return (text || '')
    .replace(/[#*_`~[\]()]/g, '')
    .replace(/- /g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

function defaultMessageState() {
  return { phase: 'idle', error: null };
}

const SPEECH_LANG = { kn: 'kn-IN', hi: 'hi-IN', en: 'en-IN' };

function tryBrowserSpeech(text, langCode, onEnd) {
  if (typeof window === 'undefined' || !window.speechSynthesis) {
    return Promise.resolve(false);
  }
  return new Promise((resolve) => {
    try {
      window.speechSynthesis.cancel();
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = SPEECH_LANG[langCode] || SPEECH_LANG.en;
      utter.onend = () => {
        onEnd?.();
        resolve(true);
      };
      utter.onerror = () => resolve(false);
      window.speechSynthesis.speak(utter);
    } catch {
      resolve(false);
    }
  });
}

export function TtsPlaybackProvider({ children }) {
  const { isTtsEnabled, currentLanguage } = useLanguageStore();
  const [tick, setTick] = useState(0);
  const messageStateRef = useRef(new Map());
  const activeMessageIdRef = useRef(null);
  const playSeqRef = useRef(0);
  const abortRef = useRef(null);
  const audioRef = useRef(null);
  const objectUrlRef = useRef(null);

  const bump = useCallback(() => setTick((n) => n + 1), []);

  const cleanupAudio = useCallback(() => {
    if (audioRef.current) {
      try {
        audioRef.current.pause();
        audioRef.current.onended = null;
        audioRef.current.onerror = null;
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

  const setMessageState = useCallback(
    (messageId, patch) => {
      if (!messageId) return;
      const prev = messageStateRef.current.get(messageId) || defaultMessageState();
      messageStateRef.current.set(messageId, { ...prev, ...patch });
      bump();
    },
    [bump]
  );

  const stopMessage = useCallback(
    (messageId) => {
      playSeqRef.current += 1;
      abortRef.current?.abort();
      abortRef.current = null;
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      cleanupAudio();
      if (messageId) {
        setMessageState(messageId, { phase: 'idle' });
      }
      activeMessageIdRef.current = null;
    },
    [cleanupAudio, setMessageState]
  );

  const playMessage = useCallback(
    async (messageId, text, language) => {
      if (!isTtsEnabled || !messageId) return;
      const cleanText = stripMarkdownForSpeech(text);
      if (!cleanText) return;

      const responseLanguage = language || currentLanguage;
      const apiLang = uiLangToApi(responseLanguage);

      if (
        activeMessageIdRef.current === messageId &&
        (messageStateRef.current.get(messageId)?.phase === 'playing' ||
          messageStateRef.current.get(messageId)?.phase === 'loading')
      ) {
        stopMessage(messageId);
        return;
      }

      playSeqRef.current += 1;
      const seq = playSeqRef.current;
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;

      cleanupAudio();
      activeMessageIdRef.current = messageId;
      setMessageState(messageId, { phase: 'loading', error: null });

      try {
        const blob = await synthesizeSpeech(cleanText, {
          language: responseLanguage,
          request_id: String(messageId),
          signal: ac.signal,
        });
        if (seq !== playSeqRef.current) return;
        if (!blob || blob.size === 0) {
          throw new Error('empty_audio');
        }
        const url = URL.createObjectURL(blob);
        objectUrlRef.current = url;
        const audio = new Audio(url);
        audioRef.current = audio;
        audio.onended = () => {
          if (seq !== playSeqRef.current) return;
          cleanupAudio();
          setMessageState(messageId, { phase: 'idle' });
          activeMessageIdRef.current = null;
        };
        audio.onerror = () => {
          if (seq !== playSeqRef.current) return;
          console.warn('TTS audio element error', { messageId, language: apiLang });
          setMessageState(messageId, {
            phase: 'idle',
            error: 'Voice playback is not available right now.',
          });
          cleanupAudio();
          activeMessageIdRef.current = null;
        };
        await audio.play();
        if (seq !== playSeqRef.current) return;
        setMessageState(messageId, { phase: 'playing', error: null });
      } catch (err) {
        if (ac.signal.aborted || seq !== playSeqRef.current) return;
        const status = err?.response?.status;
        console.warn('TTS synthesis failed', {
          messageId,
          language: apiLang,
          status: status ?? err?.message,
        });
        const uiLang = (responseLanguage || currentLanguage || 'en').toLowerCase();
        const usedBrowser = await tryBrowserSpeech(cleanText, uiLang, () => {
          if (seq !== playSeqRef.current) return;
          setMessageState(messageId, { phase: 'idle', error: null });
          activeMessageIdRef.current = null;
        });
        if (usedBrowser && seq === playSeqRef.current) {
          setMessageState(messageId, { phase: 'playing', error: null });
          return;
        }
        setMessageState(messageId, {
          phase: 'idle',
          error: err?.message || 'Voice playback is not available right now.',
        });
        cleanupAudio();
        activeMessageIdRef.current = null;
      }
    },
    [isTtsEnabled, currentLanguage, cleanupAudio, setMessageState, stopMessage]
  );

  const getMessageState = useCallback(
    (messageId) => {
      void tick;
      return messageStateRef.current.get(messageId) || defaultMessageState();
    },
    [tick]
  );

  const value = useMemo(
    () => ({
      playMessage,
      stopMessage,
      getMessageState,
    }),
    [playMessage, stopMessage, getMessageState]
  );

  return (
    <TtsPlaybackContext.Provider value={value}>{children}</TtsPlaybackContext.Provider>
  );
}

export function useTtsPlayback() {
  const ctx = useContext(TtsPlaybackContext);
  if (!ctx) {
    throw new Error('useTtsPlayback must be used within TtsPlaybackProvider');
  }
  return ctx;
}

export function useMessageTts(messageId, language) {
  const { playMessage, stopMessage, getMessageState } = useTtsPlayback();
  const { phase, error } = getMessageState(messageId);
  return {
    phase,
    error,
    isSpeaking: phase === 'playing',
    isLoading: phase === 'loading',
    speak: (text) => playMessage(messageId, text, language),
    stop: () => stopMessage(messageId),
  };
}
