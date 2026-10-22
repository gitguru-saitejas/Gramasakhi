import api from "../../../services/api";
import { mapBackendChatResponse, uiLangToApi } from "./backend-adapter";

// Align with backend LIVE_GOV_OVERALL_TIMEOUT_SECONDS (240s) plus buffer.
const CHAT_REQUEST_TIMEOUT_MS = 270_000;

async function voiceApiErrorMessage(err, fallback) {
  const status = err?.response?.status;
  if (status === 401) {
    return "Please sign in again to use voice features.";
  }
  if (status === 429) {
    return "Voice service is busy. Please wait a moment and try again.";
  }
  if (status === 503) {
    return "Voice service is temporarily unavailable.";
  }
  const detail = err?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }
  const data = err?.response?.data;
  if (data instanceof Blob) {
    try {
      const text = await data.text();
      const parsed = JSON.parse(text);
      if (typeof parsed?.detail === "string") return parsed.detail;
      if (typeof parsed?.message === "string") return parsed.message;
    } catch {
      // ignore
    }
  }
  if (typeof data?.message === "string") return data.message;
  return fallback;
}
export async function sendChatMessage(payload, { onComplete, onError } = {}) {
  try {
    const res = await api.post(
      "/chat",
      {
        message: payload.message,
        conversation_id: payload.conversation_id || null,
        language: uiLangToApi(payload.language),
        input_mode: payload.input_mode || "text",
        stt_language: payload.stt_language || null,
        voice_request_id: payload.voice_request_id || null,
      },
      { skipErrorToast: true, timeout: CHAT_REQUEST_TIMEOUT_MS }
    );
    const mapped = mapBackendChatResponse(res.data || {});
    try {
      onComplete?.(mapped);
    } catch (callbackErr) {
      onError?.(callbackErr);
    }
  } catch (err) {
    onError?.(err);
  }
}

export async function transcribeVoice(blob, { language } = {}) {
  const form = new FormData();
  form.append("audio", blob, "recording.webm");
  if (language) {
    form.append("language_hint", uiLangToApi(language));
  }
  try {
    const res = await api.post("/chat/voice/transcribe", form, {
      skipErrorToast: true,
      timeout: 120000,
      transformRequest: [
        (data, headers) => {
          if (headers && data instanceof FormData) {
            delete headers["Content-Type"];
          }
          return data;
        },
      ],
    });
    return res.data || {};
  } catch (err) {
    const message = await voiceApiErrorMessage(
      err,
      "Could not transcribe your voice. Please try again or type your question."
    );
    return { success: false, message };
  }
}

export async function synthesizeSpeech(text, { language, request_id, signal } = {}) {
  try {
    const res = await api.post(
      "/chat/voice/synthesize",
      {
        text,
        response_language: uiLangToApi(language),
        request_id: request_id || null,
      },
      {
        skipErrorToast: true,
        timeout: 120000,
        responseType: "blob",
        signal,
        validateStatus: (s) => s >= 200 && s < 300,
      }
    );
    const blob = res.data;
    const contentType = String(res.headers?.["content-type"] || "");
    if (contentType.includes("json") || contentType.includes("text/")) {
      throw new Error("tts_invalid_response");
    }
    return blob;
  } catch (err) {
    if (err?.name === "CanceledError" || err?.code === "ERR_CANCELED") {
      throw err;
    }
    const message = await voiceApiErrorMessage(
      err,
      "Voice playback is not available right now."
    );
    const wrapped = new Error(message);
    wrapped.status = err?.response?.status;
    throw wrapped;
  }
}

export { voiceApiErrorMessage };
