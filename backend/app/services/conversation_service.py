"""Conversation orchestration for GramSakhi chat (Phase 6 + history UX).
Loads history, stores messages, rewrites follow-ups, then calls the existing
RAG evidence-gated pipeline with the rewritten retrieval query.
"""
from __future__ import annotations
import json
import logging
import re
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import or_, func
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.conversation import Conversation, Message
from app.models.citizen_account import CitizenAccount
from app.services import rag as rag_service
from app.services.language_service import (
    LANG_EN,
    detect_previous_answer_transform,
    language_metadata,
    language_name,
    normalize_language_code,
    resolve_response_language,
)
from app.services.query_rewriter import rewrite_query
logger = logging.getLogger("gramsakhi.conversation")
_SCHEME_PATTERNS = [
    (re.compile(r"\bpm[\s\-]?kisan\b", re.I), "PM-KISAN"),
    (re.compile(r"\bpmay[\s\-]?g\b", re.I), "PMAY-G"),
    (re.compile(r"\bgruha\s*lakshmi\b|\bgruhalakshmi\b", re.I), "Gruha Lakshmi"),
    (re.compile(r"\bgruha\s*jyothi\b|\bgruha\s*jyoti\b", re.I), "Gruha Jyothi"),
    (re.compile(r"\bshakti\b|\u0cb6\u0c95\u0ccd\u0ca4\u0cbf|\u0936\u0915\u094d\u0924\u093f", re.I), "Shakti"),
    (re.compile(r"\bayushman\b|\bpm[\s\-]?jay\b", re.I), "Ayushman Bharat"),
]
def _as_uuid_str(value: Any) -> str:
    return str(value) if value is not None else ""
def _now() -> datetime:
    return datetime.now(timezone.utc)
def _dumps_json(value: Any) -> Optional[str]:
    if value is None:
        return None
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return None
def _loads_json(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _as_json_list(raw: Optional[str]) -> List[Any]:
    parsed = _loads_json(raw)
    return parsed if isinstance(parsed, list) else []
def generate_conversation_title(user_message: str, *, max_len: int = 72) -> str:
    """
    Deterministic short title from the ORIGINAL user message.
    Preserves KN/HI text; never uses rewritten/English retrieval queries.
    """
    text = re.sub(r"\s+", " ", (user_message or "").strip())
    if not text:
        return "New conversation"

    scheme = None
    for pat, name in _SCHEME_PATTERNS:
        if pat.search(text):
            scheme = name
            break

    topic = None
    if re.search(
        r"eligib|who is|eligible|"
        r"ಯಾರು ಅರ್ಹ|ಅರ್ಹತ|"
        r"पात्र|योग्य",
        text,
        re.I,
    ):
        topic = "Eligibility"
    elif re.search(
        r"document|ದಾಖಲ|कागज|"
        r"दस्तावेज|papers?",
        text,
        re.I,
    ):
        topic = "Documents"
    elif re.search(
        r"assist|benefit|amount|how much|"
        r"ಎಷ್ಟು|राशि|सहायता",
        text,
        re.I,
    ):
        topic = "Assistance"
    elif re.search(
        r"apply|application|ಅರ್ಜಿ|आवेदन",
        text,
        re.I,
    ):
        topic = "Application"

    if scheme and topic:
        title = f"{scheme} {topic}"
    elif scheme:
        title = f"{scheme} scheme"
    else:
        title = text.rstrip("?.! ").strip() or text

    if len(title) > max_len:
        title = title[: max_len - 1].rstrip() + "…"
    return title


def _normalize_conversation_id(conversation_id: str) -> str:
    """Reject malformed IDs before DB query (avoid driver-level 500)."""
    try:
        return str(uuid_mod.UUID(str(conversation_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        ) from exc


def get_owned_conversation(
    db: Session,
    conversation_id: str,
    citizen_account_id: str,
    *,
    include_deleted: bool = False,
) -> Conversation:
    """
    Load conversation only if owned by the citizen.
    Missing OR foreign ownership → 404 (do not reveal existence).
    Soft-deleted conversations also → 404 unless include_deleted.
    """
    conversation_id = _normalize_conversation_id(conversation_id)
    conv = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id)
        .first()
    )
    if not conv or _as_uuid_str(conv.citizen_account_id) != _as_uuid_str(citizen_account_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    if not include_deleted and (
        conv.deleted_at is not None or conv.is_active is False
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )
    return conv
def create_conversation(
    db: Session,
    citizen: CitizenAccount,
    *,
    language: Optional[str] = None,
    title: Optional[str] = None,
) -> Conversation:
    now = _now()
    conv = Conversation(
        citizen_account_id=citizen.id,
        language=normalize_language_code(language) or None,
        title=title,
        is_active=True,
        created_at=now,
        updated_at=now,
        last_message_at=None,
        deleted_at=None,
    )
    db.add(conv)
    db.flush()
    return conv
def list_conversations(
    db: Session,
    citizen_account_id: str,
    *,
    limit: int = 30,
    offset: int = 0,
) -> Tuple[List[Conversation], int]:
    lim = max(1, min(int(limit), 50))
    off = max(0, int(offset))
    base = (
        db.query(Conversation)
        .filter(
            Conversation.citizen_account_id == citizen_account_id,
            Conversation.deleted_at.is_(None),
            Conversation.is_active.is_(True),
        )
    )
    total = base.count()
    # Prefer last_message_at, fall back to updated_at
    rows = (
        base.order_by(
            func.coalesce(Conversation.last_message_at, Conversation.updated_at).desc(),
            Conversation.created_at.desc(),
        )
        .offset(off)
        .limit(lim)
        .all()
    )
    return rows, total
def search_conversations(
    db: Session,
    citizen_account_id: str,
    query: str,
    *,
    limit: int = 30,
    offset: int = 0,
) -> Tuple[List[Conversation], int]:
    q = (query or "").strip()
    if not q:
        return list_conversations(db, citizen_account_id, limit=limit, offset=offset)
    lim = max(1, min(int(limit), 50))
    off = max(0, int(offset))
    like = f"%{q}%"
    # Titles matching OR conversations with matching original user messages
    msg_conv_ids = (
        db.query(Message.conversation_id)
        .join(Conversation, Conversation.id == Message.conversation_id)
        .filter(
            Conversation.citizen_account_id == citizen_account_id,
            Conversation.deleted_at.is_(None),
            Conversation.is_active.is_(True),
            Message.role == "user",
            Message.content.ilike(like),
        )
        .distinct()
    )
    base = (
        db.query(Conversation)
        .filter(
            Conversation.citizen_account_id == citizen_account_id,
            Conversation.deleted_at.is_(None),
            Conversation.is_active.is_(True),
            or_(
                Conversation.title.ilike(like),
                Conversation.id.in_(msg_conv_ids),
            ),
        )
    )
    total = base.count()
    rows = (
        base.order_by(
            func.coalesce(Conversation.last_message_at, Conversation.updated_at).desc()
        )
        .offset(off)
        .limit(lim)
        .all()
    )
    return rows, total
def rename_conversation(
    db: Session,
    conversation_id: str,
    citizen_account_id: str,
    title: str,
) -> Conversation:
    conv = get_owned_conversation(db, conversation_id, citizen_account_id)
    cleaned = re.sub(r"\s+", " ", (title or "").strip())
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Title cannot be empty.",
        )
    conv.title = cleaned[:255]
    conv.updated_at = _now()
    db.commit()
    db.refresh(conv)
    return conv
def soft_delete_conversation(
    db: Session,
    conversation_id: str,
    citizen_account_id: str,
) -> None:
    conv = get_owned_conversation(db, conversation_id, citizen_account_id)
    now = _now()
    conv.deleted_at = now
    conv.is_active = False
    conv.updated_at = now
    db.commit()
def load_recent_messages(
    db: Session,
    conversation_id: str,
    *,
    limit: Optional[int] = None,
) -> List[Message]:
    lim = int(limit if limit is not None else settings.CONVERSATION_HISTORY_LIMIT)
    lim = max(1, lim)
    rows = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(lim)
        .all()
    )
    rows.reverse()  # chronological
    return rows
def load_messages_page(
    db: Session,
    conversation_id: str,
    *,
    limit: int = 50,
    before: Optional[datetime] = None,
) -> Tuple[List[Message], bool]:
    """
    Load recent messages first (desc), return chronological + has_more.
    Optional `before` cursor loads older messages.
    """
    lim = max(1, min(int(limit), 100))
    q = db.query(Message).filter(Message.conversation_id == conversation_id)
    if before is not None:
        q = q.filter(Message.created_at < before)
    rows = q.order_by(Message.created_at.desc()).limit(lim + 1).all()
    has_more = len(rows) > lim
    rows = rows[:lim]
    rows.reverse()
    return rows, has_more
def messages_as_history(messages: List[Message]) -> List[Dict[str, str]]:
    return [{"role": m.role, "content": m.content} for m in messages]
def message_to_dict(m: Message) -> Dict[str, Any]:
    from app.services.assistance_continuity import (
        extract_assistance_meta_from_sources,
        strip_internal_sources_for_api,
    )

    raw_sources = _as_json_list(m.sources_json)
    assistance_meta = None
    if m.role == "assistant":
        assistance_meta = extract_assistance_meta_from_sources(raw_sources)
    return {
        "id": str(m.id),
        "role": m.role,
        "content": m.content,
        "rewritten_query": m.rewritten_query,
        "language": m.language,
        "evidence_status": m.evidence_status,
        "input_mode": m.input_mode,
        "knowledge_source": m.knowledge_source,
        "sources": strip_internal_sources_for_api(raw_sources),
        "official_sources": _as_json_list(m.official_sources_json),
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "assistance_meta": assistance_meta,
    }
def conversation_to_summary(conv: Conversation) -> Dict[str, Any]:
    activity = conv.last_message_at or conv.updated_at or conv.created_at
    return {
        "id": str(conv.id),
        "title": conv.title or "New conversation",
        "language": conv.language,
        "active_scheme_context": conv.active_scheme_context,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        "last_message_at": activity.isoformat() if activity else None,
    }


def build_assistance_state_for_history(
    conv: Conversation,
    messages: List[Message],
) -> Optional[Dict[str, Any]]:
    from app.services.assistance_continuity import build_conversation_assistance_state

    return build_conversation_assistance_state(
        conversation_id=str(conv.id),
        active_scheme_context=conv.active_scheme_context,
        messages=messages,
    )


def store_message(
    db: Session,
    conversation_id: str,
    *,
    role: str,
    content: str,
    rewritten_query: Optional[str] = None,
    language: Optional[str] = None,
    evidence_status: Optional[str] = None,
    input_mode: Optional[str] = None,
    knowledge_source: Optional[str] = None,
    sources: Optional[List[Any]] = None,
    official_sources: Optional[List[Any]] = None,
) -> Message:
    msg = Message(
        conversation_id=conversation_id,
        role=role,
        content=content,
        rewritten_query=rewritten_query,
        language=language,
        evidence_status=evidence_status,
        input_mode=input_mode,
        knowledge_source=knowledge_source,
        sources_json=_dumps_json(sources) if sources is not None else None,
        official_sources_json=_dumps_json(official_sources)
        if official_sources is not None
        else None,
    )
    db.add(msg)
    db.flush()
    return msg
def _touch_conversation(conv: Conversation, *, title_if_empty: Optional[str] = None) -> None:
    now = _now()
    conv.updated_at = now
    conv.last_message_at = now
    if title_if_empty and not conv.title:
        conv.title = generate_conversation_title(title_if_empty)
def handle_citizen_chat(
    db: Session,
    citizen: CitizenAccount,
    *,
    message: str,
    conversation_id: Optional[str] = None,
    language: Optional[str] = None,
    skip_llm: bool = False,
    stt_language: Optional[str] = None,
    input_mode: Optional[str] = None,
    voice_request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full Phase 6 turn (+ Phase 7 voice metadata):
    ownership → load history → store user msg → rewrite → RAG(rewritten)
    → store assistant → return response
    Voice is only a text source; RAG/live path is unchanged.
    """
    original_query = (message or "").strip()
    if not original_query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message cannot be empty.",
        )
    mode = (input_mode or "text").strip().lower() or "text"
    created_new = False
    if conversation_id:
        conv = get_owned_conversation(db, conversation_id, str(citizen.id))
    else:
        conv = create_conversation(db, citizen, language=language)
        created_new = True
    # History BEFORE the new user turn (for rewriting / translation)
    prior = load_recent_messages(db, str(conv.id))
    history = messages_as_history(prior)
    # Per-MESSAGE language from ORIGINAL text (never rewritten retrieval query).
    # conversation.language is last-language fallback only — not a lock.
    lang_decision = resolve_response_language(
        original_query,
        request_language=None,  # UI preference must not lock response language
        conversation_language=conv.language,
        stt_language=stt_language,
        previous_response_language=conv.language,
    )
    response_language = lang_decision.response_language or LANG_EN
    # Store last detected language for weak fallback on ambiguous follow-ups
    conv.language = response_language
    _ = language  # optional UI chrome preference; ignored for answer language
    user_msg = store_message(
        db,
        str(conv.id),
        role="user",
        content=original_query,  # store exactly what the user typed
        language=response_language,
        input_mode=mode,
    )
    _touch_conversation(conv, title_if_empty=original_query)
    prev_transform = detect_previous_answer_transform(
        original_query,
        conversation_language=conv.language,
    )
    # Transform prior answer (translate / rephrase) — no RAG / no live
    if lang_decision.is_translation_only or prev_transform.apply:
        prev_assistant = next(
            (m for m in reversed(prior) if (m.role or "") == "assistant" and (m.content or "").strip()),
            None,
        )
        if not prev_assistant:
            safe = {
                LANG_EN: "Please provide the information you want me to translate.",
                "KN": "ದಯವಿಟ್ಟು ಅನುವಾದಿಸಬೇಕಾದ ಮಾಹಿತಿಯನ್ನು ನೀಡಿ.",
                "HI": "कृपया वह जानकारी दें जिसे आप अनुवाद करवाना चाहते हैं।",
            }.get(response_language, "Please provide the information you want me to translate.")
            answer = safe
            llm_invoked = False
            validated = False
            rag_result = {
                "knowledge_source": "none",
                "reason": "translation_no_previous_answer",
            }
            rewritten_query = original_query
            rewrite = {"was_rewritten": False, "method": "translation_only"}
        else:
            from app.services.llm_service import rephrase_answer, translate_answer

            target = (
                lang_decision.target_language
                or prev_transform.target_language
                or response_language
            )
            if prev_transform.mode == "rephrase":
                tr = rephrase_answer(
                    prev_assistant.content,
                    response_language=target,
                    strict_language_mode=lang_decision.strict_language_mode,
                )
            else:
                tr = translate_answer(
                    prev_assistant.content,
                    target_language=target,
                    strict_language_mode=lang_decision.strict_language_mode,
                )
            if tr.get("success"):
                answer = tr["answer"]
                llm_invoked = True
                validated = True
                rag_result = {
                    "knowledge_source": "translation",
                    "reason": "translation_only",
                    "llm_model": tr.get("model"),
                    "llm_latency_ms": tr.get("latency_ms"),
                    "response_language": tr.get("response_language") or target,
                }
            else:
                answer = tr.get("answer") or (
                    "I could not complete the translation right now. "
                    "Please try again shortly."
                )
                llm_invoked = False
                validated = False
                rag_result = {
                    "knowledge_source": "none",
                    "reason": "translation_failed",
                    "error": tr.get("error"),
                    "response_language": tr.get("response_language") or target,
                }
            rewritten_query = original_query
            rewrite = {"was_rewritten": False, "method": "translation_only"}
        db.commit()
        db.refresh(conv)
        db.refresh(user_msg)
        evidence_status = "SUPPORTED" if validated else "UNSUPPORTED"
        try:
            assistant_msg = store_message(
                db,
                str(conv.id),
                role="assistant",
                content=answer,
                language=response_language,
                evidence_status=evidence_status,
                knowledge_source=rag_result.get("knowledge_source"),
                sources=[],
                official_sources=[],
            )
            _touch_conversation(conv)
            db.commit()
            db.refresh(assistant_msg)
        except Exception as e:  # noqa: BLE001
            db.rollback()
            logger.warning("assistant message persist failed: %s", type(e).__name__)
            assistant_msg = type("M", (), {"id": None})()
        meta = language_metadata(lang_decision)
        return {
            "conversation_id": str(conv.id),
            "created_new_conversation": created_new,
            "title": conv.title,
            "message_id": str(user_msg.id),
            "assistant_message_id": (
            str(assistant_msg.id) if getattr(assistant_msg, "id", None) else None
        ),
            "original_query": original_query,
            "rewritten_query": rewritten_query,
            "was_rewritten": False,
            "rewrite_method": "translation_only",
            "answer": answer,
            "confidence": "high" if validated else "low",
            "reason": rag_result.get("reason"),
            "signals": {},
            "sources": [],
            "validated": validated,
            "llm_invoked": llm_invoked,
            "llm_model": rag_result.get("llm_model"),
            "llm_latency_ms": rag_result.get("llm_latency_ms"),
            "knowledge_source": rag_result.get("knowledge_source"),
            "live_status": None,
            "live_reason": None,
            "official_sources": [],
            "active_scheme_context": conv.active_scheme_context,
            "error": rag_result.get("error"),
            "detected_language": meta["detected_language"],
            "response_language": rag_result.get("response_language") or meta["response_language"],
            "target_language": meta["target_language"],
            "language_operation": meta.get("language_operation"),
            "input_mode": mode,
            "voice_request_id": voice_request_id,
        }
    rewrite = rewrite_query(
        original_query,
        history,
        language=response_language,
    )
    rewritten_query = rewrite["rewritten_query"] or original_query
    user_msg.rewritten_query = rewritten_query if rewrite.get("was_rewritten") else None
    from app.services.citizen_assistance import build_assistance_context
    from app.services.query_rewriter import extract_scheme_mentions, is_standalone_query

    assistance = build_assistance_context(
        original_query=original_query,
        conversation_id=str(conv.id),
        response_language=response_language,
        conversation_history=history,
        rewrite_active_scheme=rewrite.get("active_scheme"),
        conversation_active_scheme=conv.active_scheme_context,
    )
    if assistance.detected_scheme:
        conv.active_scheme_context = assistance.detected_scheme
    elif rewrite.get("active_scheme"):
        conv.active_scheme_context = rewrite["active_scheme"]
    elif is_standalone_query(original_query) and not extract_scheme_mentions(original_query):
        conv.active_scheme_context = None
    _touch_conversation(conv, title_if_empty=original_query)
    logger.info(
        "chat conversation_id=%s user_message_id=%s rewritten=%s method=%s response_language=%s",
        conv.id,
        user_msg.id,
        rewritten_query if rewrite.get("was_rewritten") else "(unchanged)",
        rewrite.get("method"),
        response_language,
    )
    # Commit conversation + user turn BEFORE long RAG/live work so a failed
    # live ingest rollback cannot wipe the conversation row (FK on messages).
    db.commit()
    db.refresh(conv)
    db.refresh(user_msg)

    from app.services.citizen_assistance import CitizenIntent
    from app.services.assistance_continuity import (
        build_message_assistance_meta,
        embed_assistance_meta_in_sources,
        strip_internal_sources_for_api,
    )
    from app.services.eligibility_questioning import (
        build_first_question_response,
        embed_session_in_sources,
        load_session_from_messages,
        schemes_differ,
        session_outcome_from,
        start_session_from_criteria,
        strip_internal_sources,
        try_handle_active_session,
    )

    prior_session = None if created_new else load_session_from_messages(prior)
    if prior_session and schemes_differ(assistance.detected_scheme, prior_session.active_scheme):
        prior_session = None

    from app.services.eligibility_explanation import (
        explain_eligibility_evaluation,
        should_explain_prior_evaluation,
    )
    from app.services.action_plan import should_action_plan_followup

    eligibility_explanation_meta: Optional[Dict[str, Any]] = None
    scheme_guidance_meta: Optional[Dict[str, Any]] = None
    action_plan_meta: Optional[Dict[str, Any]] = None

    action_plan_followup = bool(
        prior_session
        and prior_session.completed
        and prior_session.evaluation_result
        and should_action_plan_followup(original_query)
    )

    explain_followup = bool(
        prior_session
        and prior_session.completed
        and prior_session.evaluation_result
        and should_explain_prior_evaluation(
            original_query,
            prior_evaluation=prior_session.evaluation_result,
            session_completed=True,
        )
        and not action_plan_followup
    )

    elig_turn = try_handle_active_session(
        original_query=original_query,
        prior_session=prior_session,
        detected_scheme=assistance.detected_scheme,
        response_language=response_language,
    )

    eligibility_session = prior_session if (prior_session and prior_session.session_active) else None
    eligibility_payload = None
    required_information: List[str] = []
    missing_information: List[str] = []
    known_information: Dict[str, Any] = {}
    eligibility_status: Optional[str] = None
    eligibility_evaluation: Optional[Dict[str, Any]] = None

    if explain_followup and prior_session is not None:
        expl = explain_eligibility_evaluation(
            prior_session.evaluation_result or {},
            query=original_query,
            response_language=response_language,
            requested_scheme=prior_session.active_scheme or assistance.detected_scheme,
            requested_scheme_id=prior_session.scheme_id,
            evidence_validated=True,
            use_llm=not skip_llm,
        )
        rag_result = {
            "answer": expl.get("answer") or "",
            "confidence": "high",
            "reason": "eligibility_explanation",
            "signals": {},
            "sources": [],
            "validated": True,
            "llm_invoked": bool(expl.get("llm_invoked")),
            "knowledge_source": "eligibility_explanation",
            "llm_model": expl.get("llm_model"),
            "llm_latency_ms": expl.get("llm_latency_ms"),
        }
        eligibility_session = prior_session
        eligibility_payload = prior_session.criteria_snapshot
        required_information = list(prior_session.required_information or [])
        missing_information = list(prior_session.missing_information or [])
        known_information = dict(prior_session.known_information or {})
        eligibility_explanation_meta = expl
    elif elig_turn.handled and elig_turn.skip_rag:
        rag_result = {
            "answer": elig_turn.answer,
            "confidence": "high",
            "reason": "eligibility_questioning",
            "signals": {},
            "sources": [],
            "validated": True,
            "llm_invoked": False,
            "knowledge_source": elig_turn.knowledge_source,
        }
        eligibility_session = elig_turn.session
        eligibility_payload = elig_turn.eligibility_criteria
        required_information = list(elig_turn.required_information or [])
        missing_information = list(elig_turn.missing_information or [])
        known_information = dict(elig_turn.known_information or {})
    elif (
        getattr(assistance, "nlu_needs_clarification", False)
        and getattr(assistance, "nlu_clarification_prompt", None)
        and assistance.intent == CitizenIntent.CLARIFICATION
    ):
        rag_result = {
            "answer": assistance.nlu_clarification_prompt,
            "confidence": "high",
            "reason": "nlu_clarification",
            "signals": {},
            "sources": [],
            "validated": True,
            "llm_invoked": False,
            "knowledge_source": "conversation",
        }
    else:
        # Prefer context rewrite; use NLU-normalized query for vague scheme follow-ups only.
        retrieval_query = rewritten_query
        if rewrite.get("was_rewritten") and rewritten_query:
            retrieval_query = rewritten_query
        elif getattr(assistance, "normalized_query", None) and assistance.detected_scheme:
            from app.services.human_language.retrieval_routing import should_use_nlu_retrieval_query

            if should_use_nlu_retrieval_query(
                original_query,
                rewrite_was_applied=bool(rewrite.get("was_rewritten")),
            ):
                retrieval_query = assistance.normalized_query
        rag_result = rag_service.answer_with_evidence_gate(
            db,
            retrieval_query,
            language=language_name(response_language),
            conversation_context=history,
            skip_llm=skip_llm,
            enable_live_fallback=bool(settings.LIVE_GOV_FALLBACK_ENABLED),
            response_language=response_language,
            strict_language_mode=lang_decision.strict_language_mode,
            assistance_context=assistance,
        )
    from app.services.evidence_validator import SAFE_FALLBACK_ANSWER, safe_fallback_answer

    answer = rag_result.get("answer") or safe_fallback_answer(response_language)
    # Never leave English insufficient-evidence text when citizen asked in KN/HI
    if (answer or "").strip() == SAFE_FALLBACK_ANSWER and response_language in ("KN", "HI"):
        answer = safe_fallback_answer(response_language)
    validated = bool(rag_result.get("validated"))
    llm_invoked = bool(rag_result.get("llm_invoked"))
    evidence_status = "SUPPORTED" if validated and llm_invoked else (
        "SUPPORTED" if validated else "UNSUPPORTED"
    )
    if rag_result.get("reason") == "llm_unavailable":
        evidence_status = "SUPPORTED"  # validator passed; generation failed
    sources = rag_result.get("sources") or []
    official_sources = rag_result.get("official_sources") or []

    if (
        not explain_followup
        and not (elig_turn.handled and elig_turn.skip_rag)
        and validated
        and sources
    ):
        from app.services.scheme_guidance import apply_scheme_guidance, is_guidance_intent
        from app.services.action_plan import is_action_plan_intent

        if is_guidance_intent(assistance.intent) and not is_action_plan_intent(assistance.intent):
            from app.services.myscheme_service import (
                normalize_scheme_key,
                requested_scheme_identity,
                slug_hint_from_query,
            )

            scheme_identity = None
            if assistance.detected_scheme:
                scheme_identity = {
                    "scheme_name": assistance.detected_scheme,
                    "scheme_id": slug_hint_from_query(assistance.detected_scheme) or "",
                    "normalized_key": normalize_scheme_key(assistance.detected_scheme),
                }
            else:
                scheme_identity = requested_scheme_identity(original_query)
            guided = apply_scheme_guidance(
                sources=sources,
                intent=assistance.intent,
                query=original_query,
                response_language=response_language,
                scheme_identity=scheme_identity,
                evidence_validated=validated,
                use_llm=not skip_llm,
            )
            if guided.get("applied"):
                answer = guided.get("answer") or answer
                llm_invoked = bool(guided.get("llm_invoked")) or llm_invoked
                if guided.get("llm_model"):
                    rag_result["llm_model"] = guided.get("llm_model")
                if guided.get("llm_latency_ms") is not None:
                    rag_result["llm_latency_ms"] = guided.get("llm_latency_ms")
                rag_result["knowledge_source"] = "scheme_guidance"
                rag_result["reason"] = "scheme_guidance"
                scheme_guidance_meta = guided.get("guidance")
                seen_urls = {
                    str(x.get("url") or "")
                    for x in official_sources
                    if isinstance(x, dict)
                }
                for item in guided.get("official_sources") or []:
                    url = str(item.get("url") or "")
                    if url and url not in seen_urls:
                        official_sources.append(item)
                        seen_urls.add(url)

    if not (elig_turn.handled and elig_turn.skip_rag):
        from app.services.scenario_eligibility import should_attempt_scenario_evaluation

        eligibility_pipeline = (
            assistance.intent in (CitizenIntent.ELIGIBILITY, CitizenIntent.PERSONAL_ELIGIBILITY)
            or should_attempt_scenario_evaluation(original_query)
        )
        if eligibility_pipeline and rag_result.get("validated") and sources:
            from app.services.eligibility_criteria import (
                enrich_assistance_fields_from_criteria,
                extract_eligibility_criteria,
            )
            from app.services.myscheme_service import (
                normalize_scheme_key,
                requested_scheme_identity,
                slug_hint_from_query,
            )

            scheme_identity = None
            if assistance.detected_scheme:
                scheme_identity = {
                    "scheme_name": assistance.detected_scheme,
                    "scheme_id": slug_hint_from_query(assistance.detected_scheme) or "",
                    "normalized_key": normalize_scheme_key(assistance.detected_scheme),
                }
            else:
                scheme_identity = requested_scheme_identity(original_query)
            criteria = extract_eligibility_criteria(
                sources,
                scheme_identity=scheme_identity,
                query=original_query,
                language=response_language,
            )
            eligibility_payload = criteria.to_dict()
            if assistance.intent == CitizenIntent.PERSONAL_ELIGIBILITY and not criteria.rejected:
                required_information, _, missing_information = enrich_assistance_fields_from_criteria(
                    criteria
                )
                active_scheme = assistance.detected_scheme or conv.active_scheme_context or ""
                if criteria.extraction_status == "ok" and required_information and active_scheme:
                    eligibility_session = start_session_from_criteria(
                        conversation_id=str(conv.id),
                        active_scheme=active_scheme,
                        scheme_id=scheme_identity.get("scheme_id") if scheme_identity else None,
                        criteria=criteria,
                        response_language=response_language,
                        seed_text=original_query,
                    )
                    if eligibility_session is not None:
                        answer = build_first_question_response(session=eligibility_session)
                        llm_invoked = False
                        rag_result["knowledge_source"] = "eligibility_questioning"
                        required_information = list(eligibility_session.required_information)
                        missing_information = list(eligibility_session.missing_information)
                        known_information = dict(eligibility_session.known_information)
            elif assistance.intent == CitizenIntent.ELIGIBILITY or should_attempt_scenario_evaluation(
                original_query
            ):
                required_information, _, missing_information = enrich_assistance_fields_from_criteria(
                    criteria
                )
                from app.services.scenario_eligibility import try_evaluate_scenario_eligibility

                scenario_eval = try_evaluate_scenario_eligibility(
                    query=original_query,
                    criteria=criteria,
                    scheme_name=criteria.scheme_name,
                    scheme_id=criteria.scheme_id,
                    evidence_validated=validated,
                )
                if scenario_eval is not None and not explain_followup and not action_plan_followup:
                    eligibility_evaluation = scenario_eval.to_dict()
                    eligibility_status = scenario_eval.status
                    from app.services.eligibility_explanation import explain_eligibility_evaluation

                    expl = explain_eligibility_evaluation(
                        scenario_eval,
                        query=original_query,
                        response_language=response_language,
                        requested_scheme=assistance.detected_scheme or (scheme_identity or {}).get("scheme_name"),
                        requested_scheme_id=(scheme_identity or {}).get("scheme_id"),
                        evidence_validated=validated,
                        use_llm=not skip_llm,
                    )
                    answer = expl.get("answer") or answer
                    llm_invoked = bool(expl.get("llm_invoked")) or llm_invoked
                    if expl.get("llm_model"):
                        rag_result["llm_model"] = expl.get("llm_model")
                    if expl.get("llm_latency_ms") is not None:
                        rag_result["llm_latency_ms"] = expl.get("llm_latency_ms")
                    rag_result["knowledge_source"] = "eligibility_explanation"
                    rag_result["reason"] = "scenario_eligibility_evaluation"
                    eligibility_explanation_meta = expl
                    if expl.get("sources"):
                        from app.services.eligibility_explanation import merge_official_sources

                        official_sources = merge_official_sources(
                            official_sources, expl.get("sources") or []
                        )

        if (
            prior_session
            and prior_session.session_active
            and not prior_session.completed
            and eligibility_session is None
        ):
            eligibility_session = prior_session
            eligibility_payload = prior_session.criteria_snapshot
            required_information = list(prior_session.required_information)
            missing_information = list(prior_session.missing_information)
            known_information = dict(prior_session.known_information)

    sources = embed_session_in_sources(strip_internal_sources(sources), eligibility_session)
    api_sources = strip_internal_sources(sources)

    if eligibility_session and eligibility_session.completed:
        from app.services.eligibility_evaluation import evaluate_session_if_ready

        eval_result = evaluate_session_if_ready(
            eligibility_session,
            evidence_validated=validated,
        )
        if eval_result is not None:
            eligibility_evaluation = eval_result.to_dict()
            eligibility_status = eval_result.status
            eligibility_session.evaluation_result = eligibility_evaluation
            sources = embed_session_in_sources(strip_internal_sources(sources), eligibility_session)
            api_sources = strip_internal_sources(sources)
            if not explain_followup and not action_plan_followup:
                from app.services.eligibility_explanation import explain_eligibility_evaluation

                expl = explain_eligibility_evaluation(
                    eval_result,
                    query=original_query,
                    response_language=response_language,
                    requested_scheme=eligibility_session.active_scheme or assistance.detected_scheme,
                    requested_scheme_id=eligibility_session.scheme_id,
                    evidence_validated=validated,
                    use_llm=not skip_llm,
                )
                answer = expl.get("answer") or answer
                llm_invoked = bool(expl.get("llm_invoked")) or llm_invoked
                if expl.get("llm_model"):
                    rag_result["llm_model"] = expl.get("llm_model")
                if expl.get("llm_latency_ms") is not None:
                    rag_result["llm_latency_ms"] = expl.get("llm_latency_ms")
                rag_result["knowledge_source"] = "eligibility_explanation"
                rag_result["reason"] = "eligibility_explanation"
                eligibility_explanation_meta = expl
                if expl.get("sources"):
                    from app.services.eligibility_explanation import merge_official_sources

                    official_sources = merge_official_sources(
                        official_sources, expl.get("sources") or []
                    )
    if action_plan_followup and prior_session is not None:
        eligibility_session = prior_session
        eligibility_evaluation = prior_session.evaluation_result
        eligibility_status = (prior_session.evaluation_result or {}).get("status")

    if (
        not (elig_turn.handled and elig_turn.skip_rag)
        and validated
        and sources
    ):
        from app.services.action_plan import apply_action_plan, should_build_action_plan
        from app.services.myscheme_service import (
            normalize_scheme_key,
            requested_scheme_identity,
            slug_hint_from_query,
        )

        if should_build_action_plan(
            assistance.intent,
            original_query,
            has_eligibility=bool(eligibility_status or eligibility_evaluation),
        ) or action_plan_followup:
            scheme_identity = None
            if assistance.detected_scheme:
                scheme_identity = {
                    "scheme_name": assistance.detected_scheme,
                    "scheme_id": slug_hint_from_query(assistance.detected_scheme) or "",
                    "normalized_key": normalize_scheme_key(assistance.detected_scheme),
                }
            elif eligibility_session:
                scheme_identity = {
                    "scheme_name": eligibility_session.active_scheme,
                    "scheme_id": eligibility_session.scheme_id or "",
                    "normalized_key": normalize_scheme_key(eligibility_session.active_scheme or ""),
                }
            else:
                scheme_identity = requested_scheme_identity(original_query)
            plan_result = apply_action_plan(
                sources=sources,
                query=original_query,
                response_language=response_language,
                intent=assistance.intent,
                scheme_identity=scheme_identity,
                eligibility_status=eligibility_status,
                eligibility_evaluation=eligibility_evaluation,
                scheme_guidance=scheme_guidance_meta,
                known_information=known_information or None,
                conversation_id=str(conv.id),
                session_conversation_id=(
                    eligibility_session.conversation_id if eligibility_session else None
                ),
                eligibility_session_active=bool(
                    eligibility_session
                    and eligibility_session.session_active
                    and not eligibility_session.completed
                ),
                evidence_validated=validated,
                use_llm=not skip_llm,
            )
            if plan_result.get("applied"):
                answer = plan_result.get("answer") or answer
                llm_invoked = bool(plan_result.get("llm_invoked")) or llm_invoked
                if plan_result.get("llm_model"):
                    rag_result["llm_model"] = plan_result.get("llm_model")
                if plan_result.get("llm_latency_ms") is not None:
                    rag_result["llm_latency_ms"] = plan_result.get("llm_latency_ms")
                rag_result["knowledge_source"] = "action_plan"
                rag_result["reason"] = "action_plan"
                action_plan_meta = plan_result.get("action_plan")
                seen_urls = {
                    str(x.get("url") or "")
                    for x in official_sources
                    if isinstance(x, dict)
                }
                for item in plan_result.get("official_sources") or []:
                    url = str(item.get("url") or "")
                    if url and url not in seen_urls:
                        official_sources.append(item)
                        seen_urls.add(url)

    if explain_followup and eligibility_explanation_meta and prior_session is not None:
        from app.services.eligibility_explanation import merge_official_sources

        official_sources = merge_official_sources(
            official_sources,
            eligibility_explanation_meta.get("sources") or [],
        )
        eligibility_status = eligibility_explanation_meta.get("status") or (
            (prior_session.evaluation_result or {}).get("status")
        )
        eligibility_evaluation = prior_session.evaluation_result
    session_fields = session_outcome_from(eligibility_session)
    if known_information:
        session_fields["known_information"] = known_information
    from app.services.eligibility_api import eligibility_status_for_api, normalize_eligibility_status

    if eligibility_status is None and eligibility_evaluation:
        eligibility_status = normalize_eligibility_status(
            eligibility_evaluation.get("status")
        ) or eligibility_evaluation.get("status")
    api_eligibility_status = eligibility_status_for_api(eligibility_status)
    scheme_apply_meta: Optional[Dict[str, Any]] = None
    scheme_for_apply = assistance.detected_scheme or conv.active_scheme_context
    if scheme_for_apply:
        from app.services.myscheme_service import resolve_scheme_apply_targets

        apply_url = None
        apply_scheme_id = getattr(assistance, "scheme_id", None)
        if isinstance(scheme_guidance_meta, dict):
            apply_url = scheme_guidance_meta.get("application_url") or apply_url
            apply_scheme_id = scheme_guidance_meta.get("scheme_id") or apply_scheme_id
        if isinstance(action_plan_meta, dict):
            apply_url = action_plan_meta.get("application_url") or apply_url
            apply_scheme_id = action_plan_meta.get("scheme_id") or apply_scheme_id
        source_url_list = [
            str(x.get("url") or "")
            for x in (official_sources or [])
            if isinstance(x, dict) and x.get("url")
        ]
        scheme_apply_meta = resolve_scheme_apply_targets(
            scheme_for_apply,
            application_url=apply_url,
            scheme_id=apply_scheme_id,
            source_urls=source_url_list,
        )
    assistance_meta = build_message_assistance_meta(
        citizen_intent=assistance.intent.value,
        assistance_mode=assistance.assistance_mode.value,
        detected_scheme=assistance.detected_scheme,
        comparison_schemes=list(assistance.comparison_schemes or []),
        eligibility_criteria=eligibility_payload,
        required_information=required_information or None,
        missing_information=missing_information or None,
        eligibility_status=eligibility_status,
        eligibility_evaluation=eligibility_evaluation,
        eligibility_explanation=eligibility_explanation_meta,
        scheme_guidance=scheme_guidance_meta,
        action_plan=action_plan_meta,
        eligibility_session_active=session_fields.get("eligibility_session_active"),
        eligibility_question=session_fields.get("eligibility_question"),
        eligibility_completed=session_fields.get("eligibility_completed"),
        known_information=session_fields.get("known_information"),
    )
    sources = embed_session_in_sources(strip_internal_sources(sources), eligibility_session)
    sources = embed_assistance_meta_in_sources(sources, assistance_meta)
    api_sources = strip_internal_sources_for_api(sources)
    try:
        assistant_msg = store_message(
            db,
            str(conv.id),
            role="assistant",
            content=answer,
            language=response_language,
            evidence_status=evidence_status,
            knowledge_source=rag_result.get("knowledge_source"),
            sources=sources,
            official_sources=official_sources,
        )
        _touch_conversation(conv)
        db.commit()
        db.refresh(assistant_msg)
    except Exception as e:  # noqa: BLE001
        db.rollback()
        logger.warning("assistant message persist failed: %s", type(e).__name__)
        # Still return the grounded answer even if history write fails
        assistant_msg = type("M", (), {"id": None})()
    db.refresh(conv)
    db.refresh(user_msg)
    meta = language_metadata(lang_decision)
    if known_information:
        session_fields["known_information"] = known_information
    return {
        "conversation_id": str(conv.id),
        "created_new_conversation": created_new,
        "title": conv.title,
        "message_id": str(user_msg.id),
        "assistant_message_id": (
            str(assistant_msg.id) if getattr(assistant_msg, "id", None) else None
        ),
        "original_query": original_query,
        "rewritten_query": rewritten_query,
        "was_rewritten": bool(rewrite.get("was_rewritten")),
        "rewrite_method": rewrite.get("method"),
        "answer": answer,
        "confidence": rag_result.get("confidence"),
        "reason": rag_result.get("reason"),
        "signals": rag_result.get("signals"),
        "sources": api_sources,
        "validated": validated,
        "llm_invoked": llm_invoked,
        "llm_model": rag_result.get("llm_model"),
        "llm_latency_ms": rag_result.get("llm_latency_ms"),
        "knowledge_source": rag_result.get("knowledge_source"),
        "live_status": rag_result.get("live_status"),
        "live_reason": rag_result.get("live_reason"),
        "official_sources": official_sources,
        "active_scheme_context": conv.active_scheme_context,
        "error": rag_result.get("error"),
        "detected_language": meta["detected_language"],
        "response_language": rag_result.get("response_language") or meta["response_language"],
        "target_language": meta["target_language"],
        "language_operation": meta.get("language_operation"),
        "input_mode": mode,
        "voice_request_id": voice_request_id,
        "citizen_intent": assistance.intent.value,
        "nlu_intent": getattr(assistance, "nlu_intent", None),
        "normalized_query": getattr(assistance, "normalized_query", None),
        "scheme_id": getattr(assistance, "scheme_id", None),
        "assistance_mode": assistance.assistance_mode.value,
        "detected_scheme": assistance.detected_scheme,
        "comparison_schemes": list(assistance.comparison_schemes or []),
        "eligibility_criteria": eligibility_payload,
        "required_information": required_information or None,
        "missing_information": missing_information or None,
        "eligibility_status": api_eligibility_status,
        "eligibility_evaluation": eligibility_evaluation,
        "eligibility_explanation": (
            {
                "focus": eligibility_explanation_meta.get("focus"),
                "fallback": eligibility_explanation_meta.get("fallback"),
                "llm_invoked": eligibility_explanation_meta.get("llm_invoked"),
            }
            if eligibility_explanation_meta
            else None
        ),
        "scheme_guidance": scheme_guidance_meta,
        "action_plan": action_plan_meta,
        "scheme_apply": scheme_apply_meta,
        **session_fields,
    }
