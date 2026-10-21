from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: Optional[Union[str, UUID]] = None
    language: Optional[str] = None
    # Phase 7 — optional voice metadata (text chat ignores these)
    stt_language: Optional[str] = None
    input_mode: Optional[str] = None  # text | voice
    voice_request_id: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: Union[str, UUID]
    created_new_conversation: bool = False
    title: Optional[str] = None
    message_id: Optional[Union[str, UUID]] = None
    assistant_message_id: Optional[Union[str, UUID]] = None
    original_query: str
    rewritten_query: Optional[str] = None
    was_rewritten: bool = False
    answer: str
    confidence: Optional[str] = None
    reason: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    validated: bool = False
    llm_invoked: bool = False
    knowledge_source: Optional[str] = None
    live_status: Optional[str] = None
    live_reason: Optional[str] = None
    official_sources: List[Dict[str, Any]] = Field(default_factory=list)
    detected_language: Optional[str] = None
    response_language: Optional[str] = None
    target_language: Optional[str] = None
    language_operation: Optional[str] = None
    input_mode: Optional[str] = None
    voice_request_id: Optional[str] = None
    active_scheme_context: Optional[str] = None
    error: Optional[str] = None
    # Stage 6A — optional assistance metadata (additive)
    citizen_intent: Optional[str] = None
    nlu_intent: Optional[str] = None
    normalized_query: Optional[str] = None
    scheme_id: Optional[str] = None
    assistance_mode: Optional[str] = None
    detected_scheme: Optional[str] = None
    comparison_schemes: List[str] = Field(default_factory=list)
    # Stage 6B-1 — optional structured eligibility criteria (additive)
    eligibility_criteria: Optional[Dict[str, Any]] = None
    required_information: Optional[List[str]] = None
    missing_information: Optional[List[str]] = None
    # Stage 6B-2 — optional eligibility questioning metadata (additive)
    eligibility_session_active: Optional[bool] = None
    eligibility_question: Optional[str] = None
    eligibility_completed: Optional[bool] = None
    known_information: Optional[Dict[str, Any]] = None
    # Stage 6B-3 — optional deterministic evaluation (additive)
    eligibility_status: Optional[str] = None
    eligibility_evaluation: Optional[Dict[str, Any]] = None
    # Stage 6B-4 — optional explanation metadata (additive)
    eligibility_explanation: Optional[Dict[str, Any]] = None
    # Stage 6C-1 — optional scheme guidance metadata (additive)
    scheme_guidance: Optional[Dict[str, Any]] = None
    # Stage 6C-2 — optional personalized action plan (additive)
    action_plan: Optional[Dict[str, Any]] = None


class ConversationMessageOut(BaseModel):
    id: Union[str, UUID]
    role: str
    content: str
    rewritten_query: Optional[str] = None
    language: Optional[str] = None
    evidence_status: Optional[str] = None
    input_mode: Optional[str] = None
    knowledge_source: Optional[str] = None
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    official_sources: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[str] = None
    assistance_meta: Optional[Dict[str, Any]] = None


class ConversationAssistanceStateOut(BaseModel):
    active_scheme_context: Optional[str] = None
    detected_scheme: Optional[str] = None
    citizen_intent: Optional[str] = None
    assistance_mode: Optional[str] = None
    eligibility_session_active: Optional[bool] = None
    eligibility_question: Optional[str] = None
    eligibility_completed: Optional[bool] = None
    known_information: Optional[Dict[str, Any]] = None
    missing_information: Optional[List[str]] = None
    required_information: Optional[List[str]] = None
    eligibility_status: Optional[str] = None
    eligibility_evaluation: Optional[Dict[str, Any]] = None
    eligibility_explanation: Optional[Dict[str, Any]] = None
    scheme_guidance: Optional[Dict[str, Any]] = None
    action_plan: Optional[Dict[str, Any]] = None


class ConversationHistoryResponse(BaseModel):
    conversation_id: Union[str, UUID]
    title: Optional[str] = None
    language: Optional[str] = None
    active_scheme_context: Optional[str] = None
    updated_at: Optional[str] = None
    last_message_at: Optional[str] = None
    messages: List[ConversationMessageOut]
    has_more: bool = False
    assistance_state: Optional[ConversationAssistanceStateOut] = None


class ConversationSummaryOut(BaseModel):
    id: Union[str, UUID]
    title: str
    language: Optional[str] = None
    active_scheme_context: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_message_at: Optional[str] = None


class ConversationListResponse(BaseModel):
    conversations: List[ConversationSummaryOut]
    total: int
    limit: int
    offset: int
    has_more: bool = False


class ConversationCreateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    language: Optional[str] = None


class ConversationCreateResponse(BaseModel):
    id: Union[str, UUID]
    title: Optional[str] = None
    language: Optional[str] = None
    created_at: Optional[str] = None


class ConversationRenameRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class ConversationUpdateResponse(BaseModel):
    id: Union[str, UUID]
    title: str
    updated_at: Optional[str] = None
