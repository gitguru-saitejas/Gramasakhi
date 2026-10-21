import api from "../../../services/api";
import { mapBackendChatResponse, uiLangToApi } from "./backend-adapter";

// Align with backend LIVE_GOV_OVERALL_TIMEOUT_SECONDS (240s) plus buffer.
const CHAT_REQUEST_TIMEOUT_MS = 270_000;
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
}

export async function synthesizeSpeech(text, { language, request_id, signal } = {}) {
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
}
