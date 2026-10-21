/** Map GramSakhi FastAPI chat payloads to uploaded UI message shapes. */

const LANG_TO_API = { kn: "KN", hi: "HI", en: "EN" };
const LANG_FROM_API = { KN: "kn", HI: "hi", EN: "en" };

export function uiLangToApi(code) {
  const c = (code || "kn").toLowerCase();
  return LANG_TO_API[c] || "EN";
}

export function apiLangToUi(code) {
  const c = (code || "EN").toUpperCase();
  return LANG_FROM_API[c] || null;
}

function mapEvidenceSufficiency(status) {
  const s = (status || "").toUpperCase();
  if (s === "SUPPORTED") return "SUPPORTED";
  if (s === "UNSUPPORTED") return "UNSUPPORTED";
  return "PARTIAL";
}

export function normalizeSources(sources = [], officialSources = []) {
  const seen = new Set();
  const out = [];
  for (const s of [...sources, ...officialSources]) {
    const url = s?.document_url || s?.url || s?.source;
    if (!url || !/^https?:\/\//i.test(url) || seen.has(url)) continue;
    seen.add(url);
    const isPdf = Boolean(s?.is_pdf) || /\.pdf(\?|$)/i.test(url);
    out.push({
      id: url,
      url,
      title:
        s?.scheme_name ||
        s?.document_title ||
        s?.name ||
        (isPdf ? "Official scheme document (PDF)" : "Official source"),
      department: s?.department,
      is_pdf: isPdf,
    });
  }
  return out;
}

export function buildAssistantMeta(data) {
  if (!data) return null;
  const meta = {
    citizen_intent: data.citizen_intent,
    assistance_mode: data.assistance_mode,
    detected_scheme: data.detected_scheme,
    eligibility_status: data.eligibility_status,
    eligibility_evaluation: data.eligibility_evaluation,
    eligibility_explanation: data.eligibility_explanation,
    scheme_guidance: data.scheme_guidance,
    eligibility_session_active: data.eligibility_session_active,
    eligibility_question: data.eligibility_question,
    eligibility_completed: data.eligibility_completed,
    known_information: data.known_information,
    missing_information: data.missing_information,
    required_information: data.required_information,
    action_plan: data.action_plan,
  };
  const has = Object.values(meta).some(
    (v) => v != null && v !== "" && !(Array.isArray(v) && v.length === 0)
  );
  return has ? meta : null;
}

export function mapBackendChatResponse(data) {
  if (!data || typeof data !== "object") {
    return {
      message: "I don't have enough reliable information to answer that.",
      sources: [],
      schemes: [],
      grounding: { sufficiency: "UNSUPPORTED" },
      meta: null,
    };
  }
  const answer = data.answer || "I don't have enough reliable information to answer that.";
  const validated = Boolean(data?.validated);
  return {
    conversation_id: data?.conversation_id,
    title: data?.title,
    message: answer,
    language:
      apiLangToUi(data?.response_language || data?.detected_language) || undefined,
    assistant_message_id: data?.assistant_message_id || null,
    sources: normalizeSources(data?.sources, data?.official_sources),
    schemes: data?.detected_scheme
      ? [{ id: String(data.detected_scheme), name: data.detected_scheme }]
      : [],
    grounding: {
      sufficiency: validated ? "SUPPORTED" : data?.live_status === "FAILED" ? "UNSUPPORTED" : "PARTIAL",
      confidenceScore: validated ? 0.95 : undefined,
      verificationNote: validated
        ? "Verified against official government documents"
        : data?.live_reason || data?.reason || undefined,
    },
    meta: buildAssistantMeta(data),
    response_language: data?.response_language || null,
    raw: data,
  };
}

export function mapHistoryMessages(rows) {
  const list = Array.isArray(rows) ? rows : [];
  return list.map((m) => {
    if (!m || typeof m !== "object") {
      return {
        id: `msg-bad-${Date.now()}`,
        role: "assistant",
        content: "",
        timestamp: null,
        sources: [],
        schemes: [],
      };
    }
    const isAssistant = m.role === "assistant";
    const sufficiency = mapEvidenceSufficiency(m.evidence_status);
    const meta = m.assistance_meta ? { ...m.assistance_meta } : null;
    return {
      id: m.id,
      role: m.role,
      content: m.content,
      timestamp: m.created_at,
      input_mode: m.input_mode,
      language: apiLangToUi(m.language) || undefined,
      sources: isAssistant ? normalizeSources(m.sources, m.official_sources) : [],
      schemes: meta?.detected_scheme
        ? [{ id: String(meta.detected_scheme), name: meta.detected_scheme }]
        : [],
      grounding: isAssistant
        ? {
            sufficiency,
            verificationNote:
              sufficiency === "SUPPORTED" ? "Verified against official documents" : undefined,
          }
        : undefined,
      meta,
    };
  });
}

export function mapConversationSummary(row) {
  return {
    id: row.id,
    title: row.title || "Conversation",
    createdAt: row.updated_at || row.last_message_at || row.created_at,
    topic: null,
  };
}
