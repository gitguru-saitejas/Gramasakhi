'use client';

import { useState, useRef, useCallback } from 'react';
import { useLanguageStore } from '@/stores/language-store';
import { transcribeVoice } from '@/lib/api/chat-api';
import { uiLangToApi } from '@/lib/api/backend-adapter';

function pickRecorderMimeType() {
  if (typeof MediaRecorder === 'undefined') return '';
  const candidates = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ];
  for (const type of candidates) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return '';
}

function extractTranscript(data) {
  if (!data || data.success === false) {
    return {
      text: '',
      error: data?.message || 'Could not understand your voice. Please try again or type your question.',
    };
  }
  const text = (data.text || data.transcript || data.normalized_transcript || '').trim();
  if (!text) {
    return {
      text: '',
      error: data?.message || 'No speech was detected. Please try again.',
    };
  }
  return { text, error: null };
}

/**
 * Voice input via GramSakhi backend STT (MediaRecorder + /chat/voice/transcribe).
 * Falls back to browser SpeechRecognition only when backend path is unavailable.
 */
export function useVoice() {
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [error, setError] = useState(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const streamRef = useRef(null);
  const recognitionRef = useRef(null);
  const mimeTypeRef = useRef('audio/webm');
  const { getCurrentLanguageObj } = useLanguageStore();

  const stopTracks = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
  }, []);

  const startBackendRecording = useCallback(async (onResultCallback) => {
    if (isListening || isProcessing) return;
    setError(null);
    setTranscript('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = pickRecorderMimeType();
      mimeTypeRef.current = mimeType || 'audio/webm';
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      recorder.onstop = async () => {
        stopTracks();
        setIsListening(false);
        const blob = new Blob(chunksRef.current, { type: mimeTypeRef.current });
        if (!blob.size) {
          setError('No audio was captured. Hold the mic a little longer and try again.');
          return;
        }
        setIsProcessing(true);
        try {
          const langObj = getCurrentLanguageObj();
          const data = await transcribeVoice(blob, { language: langObj?.code });
          const { text, error: sttError } = extractTranscript(data);
          if (sttError) {
            setError(sttError);
            return;
          }
          setTranscript(text);
          onResultCallback?.(text, {
            input_mode: 'voice',
            stt_language: uiLangToApi(langObj?.code),
            voice_request_id: data.voice_request_id || data.request_id,
          });
        } catch {
          setError("Couldn't understand the audio. Please try again.");
        } finally {
          setIsProcessing(false);
        }
      };
      mediaRecorderRef.current = recorder;
      recorder.start(250);
      setIsListening(true);
    } catch {
      setError('Microphone access was denied.');
      setIsListening(false);
    }
  }, [getCurrentLanguageObj, stopTracks, isListening, isProcessing]);

  const stopBackendRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    } else {
      stopTracks();
      setIsListening(false);
    }
  }, [stopTracks]);

  const startBrowserRecognition = useCallback((onResultCallback) => {
    const SpeechRecognition = typeof window !== 'undefined'
      ? window.SpeechRecognition || window.webkitSpeechRecognition
      : null;
    if (!SpeechRecognition) {
      setError('Voice input is not supported in this browser.');
      return;
    }
    const langObj = getCurrentLanguageObj();
    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = langObj?.speechCode || 'en-IN';
    recognition.onresult = (event) => {
      let text = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        text += event.results[i][0].transcript;
      }
      setTranscript(text);
      if (event.results[0]?.isFinal && text.trim()) {
        onResultCallback?.(text.trim(), { input_mode: 'voice', stt_language: uiLangToApi(langObj?.code) });
      }
    };
    recognition.onerror = () => setIsListening(false);
    recognition.onend = () => setIsListening(false);
    recognitionRef.current = recognition;
    recognition.start();
    setIsListening(true);
  }, [getCurrentLanguageObj]);

  const stopListening = useCallback(() => {
    if (mediaRecorderRef.current?.state === 'recording') {
      stopBackendRecording();
      return;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
    }
    stopTracks();
    setIsListening(false);
  }, [stopBackendRecording, stopTracks]);

  const toggleListening = useCallback((onResultCallback) => {
    if (isListening) {
      stopListening();
    } else if (navigator.mediaDevices?.getUserMedia) {
      startBackendRecording(onResultCallback);
    } else {
      startBrowserRecognition(onResultCallback);
    }
  }, [isListening, startBackendRecording, startBrowserRecognition, stopListening]);

  return {
    isListening,
    isProcessing,
    transcript,
    error,
    stopListening,
    toggleListening,
  };
}
