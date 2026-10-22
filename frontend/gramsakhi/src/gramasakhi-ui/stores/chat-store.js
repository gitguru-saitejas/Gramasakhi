import { create } from "zustand";
import api from "../../services/api";
import { sendChatMessage } from "@/lib/api/chat-api";
import { mapConversationSummary, mapHistoryMessages } from "@/lib/api/backend-adapter";
import { useLanguageStore } from "@/stores/language-store";

const LS_KEY = "gramsakhiConversationId";
const FORCE_NEW_KEY = "gramsakhiForceNewChat";
const CONV_PAGE = 30;

// Backend detail strings that look technical/internal must never reach citizens.
const INTERNAL_DETAIL_PATTERN =
  /traceback|stack trace|sqlalchemy|psycopg|sqlite|exception|\.py\b|file "|nonetype|keyerror|valueerror|attributeerror/i;

function citizenSafeDetail(detail, status) {
  if (typeof detail !== "string") return null;
  const trimmed = detail.trim();
  if (!trimmed || trimmed.length > 200) return null;
  if (status >= 500 || INTERNAL_DETAIL_PATTERN.test(trimmed)) return null;
  return trimmed;
}

function friendlyError(err) {
  const status = err?.response?.status;
  const detail = citizenSafeDetail(err?.response?.data?.detail, status ?? 0);
  if (detail) return detail;
  if (status === 401) return "Please sign in again to continue.";
  if (status === 429) return "Too many requests. Please wait a moment and try again.";
  if (status === 503) return "GramSakhi is temporarily unavailable. Please try again.";
  if (err?.code === "ECONNABORTED") {
    return "The request took too long. Please try again.";
  }
  if (status >= 500) return "The server hit an error while answering. Please try once more.";
  return "GramSakhi could not complete your request. Please check your connection and try again.";
}

export const useChatStore = create((set, get) => ({
  conversations: [],
  loadingConversations: false,
  activeConversationId: null,
  messages: [],
  loadingMessages: false,
  isGenerating: false,
  currentStreamText: "",
  error: null,
  attachedFile: null,
  navigateRef: null,
  chatGeneration: 0,
  loadRequestSeq: 0,

  setNavigate: (navigate) => set({ navigateRef: navigate }),

  fetchConversations: async () => {
    set({ loadingConversations: true });
    try {
      const res = await api.get(`/chat/conversations?limit=${CONV_PAGE}&offset=0`, {
        skipErrorToast: true,
      });
      const rows = (res.data?.conversations || []).map(mapConversationSummary);
      set({ conversations: rows });
    } catch {
      set({ conversations: [] });
    } finally {
      set({ loadingConversations: false });
    }
  },

  syncRoute: async (routeConversationId) => {
    if (routeConversationId) {
      if (String(routeConversationId) === String(get().activeConversationId)) return;
      if (get().isGenerating) return;
      await get().loadConversation(routeConversationId);
      return;
    }
    if (sessionStorage.getItem(FORCE_NEW_KEY) === "1" || !localStorage.getItem(LS_KEY)) {
      set({
        activeConversationId: null,
        messages: [],
        loadingMessages: false,
        error: null,
      });
      return;
    }
    const last = localStorage.getItem(LS_KEY);
    if (last) {
      if (get().isGenerating) return;
      get().navigateRef?.(`/chat/${last}`, { replace: true });
    }
  },

  loadConversation: async (id) => {
    if (!id) return;
    const seq = get().loadRequestSeq + 1;
    set({
      loadRequestSeq: seq,
      loadingMessages: true,
      error: null,
      activeConversationId: id,
      messages: [],
      isGenerating: false,
      currentStreamText: "",
    });
    try {
      const res = await api.get(`/chat/conversations/${id}`, { skipErrorToast: true });
      if (seq !== get().loadRequestSeq) return;
      const data = res.data || {};
      const mapped = mapHistoryMessages(data.messages);
      set({
        messages: mapped,
        loadingMessages: false,
        activeConversationId: id,
      });
      localStorage.setItem(LS_KEY, id);
      sessionStorage.removeItem(FORCE_NEW_KEY);
      if (data.language) {
        const lang = data.language.toLowerCase();
        if (["kn", "hi", "en"].includes(lang)) {
          useLanguageStore.getState().setLanguage(lang);
        }
      }
    } catch {
      if (seq !== get().loadRequestSeq) return;
      set({
        messages: [],
        loadingMessages: false,
        error: "We couldn't load this conversation. Please try again.",
      });
    }
  },

  setAttachedFile: (file) => set({ attachedFile: file }),
  clearAttachedFile: () => set({ attachedFile: null }),

  newConversation: () => {
    const gen = get().chatGeneration + 1;
    sessionStorage.setItem(FORCE_NEW_KEY, "1");
    localStorage.removeItem(LS_KEY);
    set({
      chatGeneration: gen,
      activeConversationId: null,
      messages: [],
      error: null,
      isGenerating: false,
      currentStreamText: "",
      attachedFile: null,
    });
    get().navigateRef?.("/chat", { replace: true });
  },

  selectConversation: (id) => {
    if (!id) return;
    if (String(id) === String(get().activeConversationId)) return;
    set({
      chatGeneration: get().chatGeneration + 1,
      error: null,
      isGenerating: false,
      currentStreamText: "",
    });
    sessionStorage.removeItem(FORCE_NEW_KEY);
    get().navigateRef?.(`/chat/${id}`);
    get().loadConversation(id);
  },

  selectConversationByTopic: () => {
    get().newConversation();
  },

  clearChat: () => {
    get().newConversation();
  },

  resetSession: () => {
    sessionStorage.removeItem(FORCE_NEW_KEY);
    localStorage.removeItem(LS_KEY);
    set({
      conversations: [],
      activeConversationId: null,
      messages: [],
      loadingConversations: false,
      loadingMessages: false,
      isGenerating: false,
      currentStreamText: "",
      error: null,
      attachedFile: null,
      chatGeneration: get().chatGeneration + 1,
    });
  },

  requestLanguageTransform: (targetLangCode) => {
    const code = (targetLangCode || "").toLowerCase();
    const commands = {
      en: "English please",
      kn: "Kannada please",
      hi: "Hindi please",
    };
    const phrase = commands[code];
    if (!phrase) return false;
    const messages = get().messages || [];
    const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant" && m.content?.trim());
    if (!lastAssistant) return false;
    if (get().isGenerating) return false;
    get().sendMessage(phrase, code);
    return true;
  },

  sendMessage: async (text, language = "kn", voiceOpts = {}) => {
    if (!text?.trim()) return;
    if (get().isGenerating) return;

    const gen = get().chatGeneration;
    set({
      isGenerating: true,
      currentStreamText: "",
      error: null,
      attachedFile: null,
    });

    const userMsg = {
      id: `msg-usr-${Date.now()}`,
      role: "user",
      content: text.trim(),
      timestamp: new Date().toISOString(),
      input_mode: voiceOpts.input_mode || "text",
    };

    set((state) => ({
      messages: [...state.messages, userMsg],
    }));

    const assistantTempId = `msg-ast-${Date.now()}`;

    const finishGenerating = () => {
      if (gen !== get().chatGeneration) return;
      set({ isGenerating: false, currentStreamText: "" });
    };

    try {
      await sendChatMessage(
        {
          conversation_id: get().activeConversationId,
          message: text.trim(),
          language,
          input_mode: voiceOpts.input_mode || "text",
          stt_language: voiceOpts.stt_language,
          voice_request_id: voiceOpts.voice_request_id,
        },
        {
          onComplete: (data) => {
            if (gen !== get().chatGeneration) {
              finishGenerating();
              return;
            }

            const assistantId =
              data.assistant_message_id ||
              data.raw?.assistant_message_id ||
              assistantTempId;

            const responseLang =
              data.language ||
              (data.response_language
                ? String(data.response_language).toLowerCase()
                : undefined);

            if (responseLang && ["kn", "hi", "en"].includes(responseLang)) {
              useLanguageStore.getState().setLanguage(responseLang);
            }

            const finalAssistantMsg = {
              id: assistantId,
              role: "assistant",
              content: data.message,
              timestamp: new Date().toISOString(),
              sources: data.sources || [],
              schemes: data.schemes || [],
              grounding: data.grounding,
              meta: data.meta,
              rawResponse: data.raw || null,
              language: responseLang,
            };

            const prevConversationId = get().activeConversationId;
            const convId = data.conversation_id || prevConversationId;

            set((state) => ({
              messages: [...state.messages, finalAssistantMsg],
              isGenerating: false,
              currentStreamText: "",
              activeConversationId: convId || state.activeConversationId,
            }));

            if (data.conversation_id) {
              localStorage.setItem(LS_KEY, data.conversation_id);
              sessionStorage.removeItem(FORCE_NEW_KEY);
              const nav = get().navigateRef;
              if (nav && String(prevConversationId) !== String(data.conversation_id)) {
                nav(`/chat/${data.conversation_id}`, { replace: true });
              }
            }

            get().fetchConversations();
          },
          onError: (err) => {
            if (gen !== get().chatGeneration) {
              finishGenerating();
              return;
            }
            set({
              isGenerating: false,
              currentStreamText: "",
              error: friendlyError(err),
            });
          },
        }
      );
    } finally {
      if (gen === get().chatGeneration && get().isGenerating) {
        set({
          isGenerating: false,
          currentStreamText: "",
          error:
            get().error ||
            "GramSakhi could not finish updating the chat. Please try again.",
        });
      }
    }
  },
}));
