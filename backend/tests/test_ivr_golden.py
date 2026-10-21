"""Phase 6 — IVR golden journey (simulated telephony, real IVR + conversation pipeline).

Uses STT/TTS test hooks for controlled transcripts and audio while exercising
production IVR endpoints, state machine, and conversation_service.handle_citizen_chat.
RAG is stubbed at the evidence gate only (same pattern as conversation service tests).
"""

from __future__ import annotations

import os
import re
import time
import unittest
from dataclasses import dataclass, field
from typing import Any, Optional
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core import security
from app.core.config import settings
from app.database.session import Base, get_db
from app.main import app
from app.models import citizen_account, user, rag, audit, conversation  # noqa: F401
from app.models.conversation import Conversation, Message
from app.models.citizen_account import CitizenAccount
from app.services import rag as rag_service
from app.services.ivr.audio_token_store import get_audio_token_store, reset_audio_token_store
from app.services.ivr.call_state import IvrCallState, get_state
from app.services.ivr.language_session import get_conversation_id, get_session_store, reset_session_store
from app.services.ivr.stt_adapter import transcribe_ivr_audio
from app.services.voice import stt_service, tts_service
from app.services.voice.audio_utils import make_tone_wav

CALL_GOLDEN = "CA_GOLDEN_AAAAAAAAAAAAAAAAAAAAAAAA"
CALL_A = "CA_ISO_AAAAAAAAAAAAAAAAAAAAAAAAAA"
CALL_B = "CA_ISO_BBBBBBBBBBBBBBBBBBBBBBBBBBBB"
FAKE_MP3 = b"\xff\xfb" + b"\x00" * 64


@dataclass
class TurnTimings:
    stt_ms: float = 0.0
    chat_ms: float = 0.0
    tts_ms: float = 0.0

    @property
    def total_ms(self) -> float:
        return self.stt_ms + self.chat_ms + self.tts_ms


@dataclass
class IvrHarness:
    client: TestClient
    timings: list[TurnTimings] = field(default_factory=list)
    tts_languages: list[str] = field(default_factory=list)

    def select_english(self, call_sid: str) -> None:
        resp = self.client.get(
            "/api/ivr/language",
            params={"CallSid": call_sid, "digits": "3"},
        )
        IvrHarness.assert200(resp)
        if get_state(call_sid) != IvrCallState.READY_FOR_INPUT:
            raise AssertionError(f"expected READY_FOR_INPUT got {get_state(call_sid)}")

    def stt_with_text(self, call_sid: str, text: str) -> None:
        stt_service.set_test_transcribe_hook(
            lambda *a, **k: {"success": True, "text": text, "request_id": f"stt-{len(self.timings)}"}
        )
        t0 = time.perf_counter()
        outcome = transcribe_ivr_audio(call_sid, audio_bytes=make_tone_wav(0.15))
        stt_ms = (time.perf_counter() - t0) * 1000
        if outcome.failure is not None:
            raise AssertionError(f"STT failed: {outcome.failure}")
        if get_state(call_sid) != IvrCallState.TRANSCRIBING:
            raise AssertionError(f"expected TRANSCRIBING got {get_state(call_sid)}")
        turn = TurnTimings(stt_ms=stt_ms)
        self.timings.append(turn)

    def chat_and_tts(self, call_sid: str) -> dict[str, Any]:
        turn = self.timings[-1]
        t0 = time.perf_counter()
        chat_resp = self.client.post("/api/ivr/chat", json={"CallSid": call_sid})
        turn.chat_ms = (time.perf_counter() - t0) * 1000
        IvrHarness.assert200(chat_resp)
        body = chat_resp.json()
        if not body.get("success"):
            raise AssertionError(f"chat failed: {body}")
        if get_state(call_sid) != IvrCallState.SYNTHESIZING:
            raise AssertionError(f"expected SYNTHESIZING got {get_state(call_sid)}")

        captured: dict[str, str] = {}

        def _tts_hook(text, language=None, **kwargs):
            captured["language"] = (language or "").upper()
            self.tts_languages.append(captured["language"])
            return {"success": True, "audio": FAKE_MP3, "mime_type": "audio/mpeg"}

        tts_service.set_test_synthesize_hook(_tts_hook)
        t0 = time.perf_counter()
        tts_resp = self.client.post("/api/ivr/tts", json={"CallSid": call_sid})
        turn.tts_ms = (time.perf_counter() - t0) * 1000
        IvrHarness.assert200(tts_resp)
        tts_body = tts_resp.json()
        if not tts_body.get("success"):
            raise AssertionError(f"tts failed: {tts_body}")
        if get_state(call_sid) != IvrCallState.PLAYING_RESPONSE:
            raise AssertionError(f"expected PLAYING_RESPONSE got {get_state(call_sid)}")
        token = (tts_body.get("audio_url") or "").rsplit("/", 1)[-1]
        if self.client.get(f"/api/ivr/audio/{token}").status_code != 200:
            raise AssertionError("audio token fetch failed")
        captured["token"] = token
        return {**body, **captured}

    def advance_continue_menu(self, call_sid: str) -> None:
        resp = self.client.get("/api/ivr/continue", params={"CallSid": call_sid})
        IvrHarness.assert200(resp)
        if get_state(call_sid) != IvrCallState.ASK_CONTINUE:
            raise AssertionError(f"expected ASK_CONTINUE got {get_state(call_sid)}")

    def continue_yes(self, call_sid: str) -> None:
        resp = self.client.post(
            "/api/ivr/continue",
            json={"CallSid": call_sid, "digits": "1"},
        )
        IvrHarness.assert200(resp)
        if not resp.json().get("continue_loop"):
            raise AssertionError("expected continue_loop")
        if get_state(call_sid) != IvrCallState.READY_FOR_INPUT:
            raise AssertionError(f"expected READY_FOR_INPUT got {get_state(call_sid)}")

    def end_call(self, call_sid: str) -> None:
        resp = self.client.post(
            "/api/ivr/continue",
            json={"CallSid": call_sid, "digits": "2"},
        )
        IvrHarness.assert200(resp)
        if not resp.json().get("end_call"):
            raise AssertionError("expected end_call")
        if get_session_store().session_exists(call_sid):
            raise AssertionError("session should be terminated")

    def full_turn(self, call_sid: str, transcript: str, *, loop: bool = True) -> dict[str, Any]:
        self.stt_with_text(call_sid, transcript)
        out = self.chat_and_tts(call_sid)
        self.advance_continue_menu(call_sid)
        if loop:
            self.continue_yes(call_sid)
        return out

    @staticmethod
    def assert200(resp) -> None:
        if resp.status_code != 200:
            raise AssertionError(f"expected 200 got {resp.status_code}: {resp.text}")


def _rag_for_golden(db, query, **kwargs):
    q = (query or "").lower()
    base = {
        "confidence": "high",
        "reason": "ok",
        "sources": [
            {
                "scheme_name": "Gruha Lakshmi",
                "page": 1,
                "source": "https://www.myscheme.gov.in/schemes/gruha-lakshmi",
            }
        ],
        "validated": True,
        "llm_invoked": True,
    }
    if "pmsby" in q or "pradhan mantri suraksha" in q:
        return {
            **base,
            "answer": "PMSBY is a low-cost accidental death insurance scheme for bank account holders.",
            "sources": [{"scheme_name": "PMSBY", "page": 1, "source": "https://www.myscheme.gov.in/"}],
        }
    if "document" in q or "what documents" in q:
        return {
            **base,
            "answer": "Typical documents include Aadhaar, ration card, and bank passbook for Gruha Lakshmi.",
        }
    if "apply" in q or "how can i apply" in q or "how do i get" in q:
        return {
            **base,
            "answer": "You can apply for Gruha Lakshmi through Seva Sindhu or the official Karnataka portal.",
        }
    if "gruha" in q or "lakshmi" in q:
        return {
            **base,
            "answer": "Gruha Lakshmi is a Karnataka scheme providing financial support to eligible women heads of household.",
        }
    if "thank" in q:
        return {**base, "answer": "You are welcome. For official updates, check myscheme.gov.in."}
    return {**base, "answer": f"Evidence-backed note for: {query}"}


class IvrGoldenTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_path = "test_ivr_golden.db"
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except OSError:
                pass
        cls.engine = create_engine(
            f"sqlite:///{cls.db_path}", connect_args={"check_same_thread": False}
        )
        Base.metadata.create_all(bind=cls.engine)
        cls.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=cls.engine)
        settings.QUERY_REWRITE_USE_OLLAMA = False

        def _override_db():
            db = cls.SessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = _override_db
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.engine.dispose()
        if os.path.exists(cls.db_path):
            try:
                os.remove(cls.db_path)
            except OSError:
                pass

    def setUp(self):
        reset_session_store()
        reset_audio_token_store()
        stt_service.set_test_transcribe_hook(None)
        tts_service.set_test_synthesize_hook(None)
        db = self.SessionLocal()
        db.query(Message).delete()
        db.query(Conversation).delete()
        db.query(CitizenAccount).delete()
        acct = CitizenAccount(
            phone_number="+910000000088",
            password_hash=security.get_password_hash("ivr-golden"),
            display_name="IVR Bridge Golden",
        )
        db.add(acct)
        db.commit()
        db.refresh(acct)
        self.bridge_id = str(acct.id)
        db.close()
        self._acct = patch.object(settings, "IVR_CITIZEN_ACCOUNT_ID", self.bridge_id)
        self._pub = patch.object(settings, "IVR_PUBLIC_BASE_URL", "https://api.gramsakhi.example.in")
        self._turns = patch.object(settings, "IVR_MAX_TURNS", 12)
        self._acct.start()
        self._pub.start()
        self._turns.start()
        self.harness = IvrHarness(client=self.client)
        self._rag_patch = patch.object(rag_service, "answer_with_evidence_gate", side_effect=_rag_for_golden)
        self._rag_patch.start()
        self._translate_patch = patch(
            "app.services.llm_service.translate_answer",
            side_effect=self._fake_translate,
        )
        self._rephrase_patch = patch(
            "app.services.llm_service.rephrase_answer",
            side_effect=self._fake_rephrase,
        )
        self._translate_patch.start()
        self._rephrase_patch.start()

    def tearDown(self):
        self._rephrase_patch.stop()
        self._translate_patch.stop()
        self._rag_patch.stop()
        self._turns.stop()
        self._pub.stop()
        self._acct.stop()

    @staticmethod
    def _fake_translate(text, *, target_language, **kwargs):
        lang = (target_language or "EN").upper()
        if lang == "KN":
            answer = "ಗ್ರುಹ ಲಕ್ಷ್ಮಿ ಯೋಜನೆಯ ಸಂಕ್ಷಿಪ್ತ ವಿವರ."
        elif lang == "HI":
            answer = "Gruha Lakshmi yojana ka sara vivaran Hindi mein."
        else:
            answer = text
        return {
            "success": True,
            "answer": answer,
            "response_language": lang,
            "model": "test",
            "latency_ms": 1,
        }

    @staticmethod
    def _fake_rephrase(text, *, target_language=None, **kwargs):
        lang = (target_language or "EN").upper()
        simplified = "Simple: apply on Seva Sindhu with Aadhaar and ration card."
        return {
            "success": True,
            "answer": simplified if lang == "EN" else simplified,
            "response_language": lang,
            "model": "test",
            "latency_ms": 1,
        }


class TestIvrGoldenConversation(IvrGoldenTestBase):
    def test_ivr_golden_conversation(self):
        sid = CALL_GOLDEN
        self.harness.select_english(sid)
        conv_ids: list[str] = []

        steps = [
            ("Tell me about Gruha Lakshmi.", "gruha"),
            ("How can I apply?", "apply"),
            ("Documents?", "document"),
            ("Kannada please", "translation"),
            ("Explain that simply", "rephrase"),
            ("English please", "translation"),
        ]
        for transcript, kind in steps:
            out = self.harness.full_turn(sid, transcript)
            conv_ids.append(out.get("conversation_id") or "")
            if kind == "gruha":
                self.assertIn("Gruha Lakshmi", out.get("response_text", ""))
            if kind == "translation" and "Kannada" in transcript:
                self.assertEqual((out.get("response_language") or "").upper(), "KN")
            if kind == "rephrase":
                self.assertIn("Simple:", out.get("response_text", ""))

        self.assertTrue(all(cid and cid == conv_ids[0] for cid in conv_ids))
        self.assertEqual(get_conversation_id(sid), conv_ids[0])

        self.harness.stt_with_text(sid, "Thank you")
        thanks = self.harness.chat_and_tts(sid)
        self.assertTrue(thanks.get("success"))
        self.harness.advance_continue_menu(sid)
        self.harness.end_call(sid)

        db = self.SessionLocal()
        msgs = db.query(Message).filter(Message.conversation_id == conv_ids[0]).count()
        db.close()
        self.assertGreaterEqual(msgs, 10)


class TestIvrCallIsolation(IvrGoldenTestBase):
    def test_ivr_call_isolation(self):
        self.harness.select_english(CALL_A)
        self.harness.select_english(CALL_B)

        a1 = self.harness.full_turn(CALL_A, "Tell me about Gruha Lakshmi.")
        b1 = self.harness.full_turn(CALL_B, "Tell me about PMSBY.")

        conv_a = a1["conversation_id"]
        conv_b = b1["conversation_id"]
        self.assertNotEqual(conv_a, conv_b)

        a2 = self.harness.full_turn(CALL_A, "How can I apply?")
        self.assertEqual(a2["conversation_id"], conv_a)
        self.assertIn("apply", a2["response_text"].lower())

        db = self.SessionLocal()
        titles_a = db.query(Conversation).filter(Conversation.id == conv_a).first()
        titles_b = db.query(Conversation).filter(Conversation.id == conv_b).first()
        db.close()
        self.assertIsNotNone(titles_a)
        self.assertIsNotNone(titles_b)
        self.assertNotEqual(titles_a.id, titles_b.id)


class TestIvrLanguageSwitch(IvrGoldenTestBase):
    def test_ivr_language_switch_en_kn_en(self):
        sid = CALL_GOLDEN
        self.harness.select_english(sid)
        self.harness.full_turn(sid, "Tell me about Gruha Lakshmi.")
        self.assertEqual(get_session_store().get_language(sid), "en")

        out_kn = self.harness.full_turn(sid, "Kannada please")
        self.assertEqual((out_kn.get("response_language") or "").upper(), "KN")
        self.assertEqual(get_session_store().get_language(sid), "en")

        out_en = self.harness.full_turn(sid, "English please")
        self.assertEqual((out_en.get("response_language") or "").upper(), "EN")

    def test_ivr_language_switch_en_hi_en(self):
        sid = "CA_GOLDEN_HHHHHHHHHHHHHHHHHHHHHHHH"
        self.client.get("/api/ivr/language", params={"CallSid": sid, "digits": "2"})
        self.assertEqual(get_session_store().get_language(sid), "hi")
        self.harness.full_turn(sid, "Tell me about Gruha Lakshmi.")
        out = self.harness.full_turn(sid, "Hindi please")
        self.assertIn("Hindi", out.get("response_text", "") + out.get("response_language", ""))


class TestIvrTtsLifecycle(IvrGoldenTestBase):
    def test_ivr_tts_lifecycle_en_kn_hi(self):
        sid_en = "CA_TTS_EN_EN_EN_EN_EN_EN_EN_EN_EN"
        self.client.get("/api/ivr/language", params={"CallSid": sid_en, "digits": "3"})
        out_en = self.harness.full_turn(sid_en, "Tell me about Gruha Lakshmi.", loop=False)
        self.assertTrue(out_en.get("token"))
        self.assertEqual(self.harness.tts_languages[-1], "EN")

        sid_kn = "CA_TTS_KN_KN_KN_KN_KN_KN_KN_KN_KN"
        reset_session_store()
        reset_audio_token_store()
        self.harness = IvrHarness(client=self.client)
        self.client.get("/api/ivr/language", params={"CallSid": sid_kn, "digits": "1"})
        self.harness.full_turn(sid_kn, "Tell me about Gruha Lakshmi.", loop=True)
        out_kn = self.harness.full_turn(sid_kn, "Kannada please", loop=False)
        self.assertEqual((out_kn.get("response_language") or "").upper(), "KN")
        self.assertEqual(self.harness.tts_languages[-1], "KN")

        sid_hi = "CA_TTS_HI_HI_HI_HI_HI_HI_HI_HI_HI"
        reset_session_store()
        reset_audio_token_store()
        self.harness = IvrHarness(client=self.client)
        self.client.get("/api/ivr/language", params={"CallSid": sid_hi, "digits": "2"})
        self.harness.full_turn(sid_hi, "Tell me about Gruha Lakshmi.", loop=True)
        out_hi = self.harness.full_turn(sid_hi, "Hindi please", loop=False)
        self.assertIn("HI", (out_hi.get("response_language") or "").upper())
        self.assertEqual(self.harness.tts_languages[-1], "HI")

        token_a = get_audio_token_store().issue(call_sid=CALL_A, data=FAKE_MP3, mime_type="audio/mpeg")
        token_b = get_audio_token_store().issue(call_sid=CALL_B, data=FAKE_MP3, mime_type="audio/mpeg")
        get_audio_token_store().revoke_for_call_sid(CALL_A)
        self.assertIsNone(get_audio_token_store().get(token_a))
        self.assertIsNotNone(get_audio_token_store().get(token_b))


class TestIvrFailureRecovery(IvrGoldenTestBase):
    def test_stt_failure_recovers_then_good_turn(self):
        sid = CALL_GOLDEN
        self.harness.select_english(sid)
        stt_service.set_test_transcribe_hook(
            lambda *a, **k: {"success": False, "error": "stt_failed"}
        )
        transcribe_ivr_audio(sid, audio_bytes=make_tone_wav(0.1))
        self.assertEqual(get_state(sid), IvrCallState.READY_FOR_INPUT)
        out = self.harness.full_turn(sid, "Tell me about Gruha Lakshmi.")
        self.assertTrue(out.get("success"))

    def test_empty_transcript_handled(self):
        sid = CALL_GOLDEN
        self.harness.select_english(sid)
        stt_service.set_test_transcribe_hook(
            lambda *a, **k: {"success": True, "text": "   ", "request_id": "e1"}
        )
        outcome = transcribe_ivr_audio(sid, audio_bytes=make_tone_wav(0.1))
        self.assertIsNotNone(outcome.failure)
        self.assertEqual(get_state(sid), IvrCallState.READY_FOR_INPUT)

    def test_chat_failure_recovers(self):
        sid = CALL_GOLDEN
        self.harness.select_english(sid)
        self.harness.stt_with_text(sid, "Tell me about Gruha Lakshmi.")
        with patch.object(rag_service, "answer_with_evidence_gate", side_effect=RuntimeError("boom")):
            resp = self.client.post("/api/ivr/chat", json={"CallSid": sid})
        self.assertEqual(resp.status_code, 503)
        self.assertEqual(get_state(sid), IvrCallState.READY_FOR_INPUT)
        out = self.harness.full_turn(sid, "How can I apply?")
        self.assertTrue(out.get("success"))

    def test_tts_failure_does_not_stick(self):
        sid = CALL_GOLDEN
        self.harness.select_english(sid)
        self.harness.stt_with_text(sid, "Tell me about Gruha Lakshmi.")
        self.client.post("/api/ivr/chat", json={"CallSid": sid})
        tts_service.set_test_synthesize_hook(
            lambda *a, **k: {"success": False, "error": "tts_failed"}
        )
        resp = self.client.post("/api/ivr/tts", json={"CallSid": sid})
        self.assertEqual(resp.status_code, 503)
        tts_service.set_test_synthesize_hook(
            lambda *a, **k: {"success": True, "audio": FAKE_MP3, "mime_type": "audio/mpeg"}
        )
        retry = self.client.post("/api/ivr/tts", json={"CallSid": sid})
        self.assertTrue(retry.json().get("success"))

    def test_invalid_and_expired_audio_token(self):
        self.assertEqual(self.client.get("/api/ivr/audio/not!!!valid").status_code, 404)
        token = get_audio_token_store().issue(call_sid=CALL_A, data=FAKE_MP3, mime_type="audio/mpeg")
        entry = get_audio_token_store().get(token)
        assert entry is not None
        entry.expires_at = time.time() - 1
        self.assertEqual(self.client.get(f"/api/ivr/audio/{token}").status_code, 404)

    def test_unknown_callsid_rejected(self):
        resp = self.client.post("/api/ivr/chat", json={"CallSid": "CA_UNKNOWN_XXXXXXXXXXXXXXXXXXXXXXXX"})
        self.assertIn(resp.status_code, {400, 404, 409, 503})


class TestIvrShortNaturalSpeech(IvrGoldenTestBase):
    def test_short_followups_use_context(self):
        sid = CALL_GOLDEN
        self.harness.select_english(sid)
        self.harness.full_turn(sid, "Tell me about Gruha Lakshmi.")
        for short in (
            "How do I get this?",
            "What documents?",
            "Can I apply?",
            "Who gets it?",
            "How much?",
        ):
            out = self.harness.full_turn(sid, short)
            self.assertTrue(out.get("success"))
            self.assertNotIn("PMSBY", out.get("response_text", ""))


class TestIvrGoldenPerformance(IvrGoldenTestBase):
    def test_turn_timing_samples(self):
        sid = CALL_GOLDEN
        self.harness.select_english(sid)
        for _ in range(3):
            self.harness.full_turn(sid, "Tell me about Gruha Lakshmi.")
        totals = [t.total_ms for t in self.harness.timings]
        self.assertEqual(len(totals), 3)
        for t in totals:
            self.assertLess(t, 120_000)


if __name__ == "__main__":
    unittest.main()
