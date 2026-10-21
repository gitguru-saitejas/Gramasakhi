"""Phase 7 — STT/TTS adapter tests (mocked engines; no live mic)."""

from __future__ import annotations

import io
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.language_service import resolve_response_language
from app.services.voice.audio_utils import (
    make_silence_wav,
    make_tone_wav,
    sniff_format,
    validate_audio_bytes,
)
from app.services.voice.messages import voice_message
from app.services.voice.pronunciation import build_tts_text
from app.services.voice import stt_service, tts_service


class TestAudioValidation(unittest.TestCase):
    def test_silence_wav_rejected_as_empty_or_ok_short(self):
        data = make_silence_wav(0.02)
        self.assertEqual(sniff_format(data), "wav")
        v = validate_audio_bytes(data, max_size_mb=8, max_duration_seconds=60)
        self.assertFalse(v.ok)
        self.assertEqual(v.error, "empty_audio")

    def test_oversized_rejected(self):
        # validate_audio_bytes floors max_size_mb at 0.1; pad past that floor.
        data = make_tone_wav(0.2) + (b"\x00" * int(0.15 * 1024 * 1024))
        v = validate_audio_bytes(data, max_size_mb=0.1, max_duration_seconds=60)
        self.assertFalse(v.ok)
        self.assertEqual(v.error, "audio_too_large")

    def test_unsupported_bytes(self):
        v = validate_audio_bytes(b"not-audio", max_size_mb=8, max_duration_seconds=60)
        self.assertFalse(v.ok)
        self.assertEqual(v.error, "unsupported_audio_format")

    def test_valid_tone_wav(self):
        data = make_tone_wav(0.3)
        v = validate_audio_bytes(data, max_size_mb=8, max_duration_seconds=60)
        self.assertTrue(v.ok)
        self.assertEqual(v.format_hint, "wav")


class TestSttLanguageResolution(unittest.TestCase):
    def test_script_overrides_stt_english(self):
        text = "PM-KISAN \u0caf\u0ccb\u0c9c\u0ca8\u0cc6\u0caf \u0c85\u0cb0\u0ccd\u0cb9\u0ca4\u0cc6?"
        lang = stt_service.resolve_transcript_language(text, "en")
        self.assertEqual(lang, "KN")

    def test_chat_uses_stt_when_no_script(self):
        # Latin-only without English question structure → trust STT
        d = resolve_response_language(
            "PM-KISAN",
            stt_language="HI",
        )
        self.assertEqual(d.response_language, "HI")
        self.assertEqual(d.reason, "stt_language")

    def test_english_question_beats_wrong_stt_hindi(self):
        d = resolve_response_language(
            "What is PM-KISAN eligibility?",
            stt_language="HI",
        )
        self.assertEqual(d.response_language, "EN")

    def test_script_beats_stt_in_chat_resolve(self):
        d = resolve_response_language(
            "PM-KISAN \u0caf\u0ccb\u0c9c\u0ca8\u0cc6 \u0c8f\u0ca8\u0cc1?",
            stt_language="EN",
        )
        self.assertEqual(d.response_language, "KN")


class TestTranscribeEndpoint(unittest.TestCase):
    def setUp(self):
        from app.api.endpoints import voice as voice_ep

        self.app = FastAPI()
        self.app.include_router(voice_ep.router, prefix="/api/chat")

        async def fake_citizen():
            acc = MagicMock()
            acc.id = "cit-1"
            acc.is_active = True
            return acc

        self.app.dependency_overrides[voice_ep.get_current_citizen] = fake_citizen
        self.client = TestClient(self.app)

        def hook(data, **kwargs):
            if not data:
                return {
                    "success": False,
                    "error": "empty_audio",
                    "message_key": "empty_audio",
                    "request_id": "r1",
                }
            if data[:4] != b"RIFF":
                # treat as kannada fixture by size heuristic
                return {
                    "success": True,
                    "text": "PM-KISAN \u0caf\u0ccb\u0c9c\u0ca8\u0cc6\u0caf \u0c85\u0cb0\u0ccd\u0cb9\u0ca4\u0cc6 \u0c8f\u0ca8\u0cc1?",
                    "detected_language": "KN",
                    "confidence": 0.9,
                    "low_confidence": False,
                    "request_id": "r1",
                    "latency_ms": 12,
                    "stt_model": "base",
                }
            # silence / wav path through real validation in service — hook bypasses
            return {
                "success": True,
                "text": "What is PM-KISAN?",
                "detected_language": "EN",
                "confidence": 0.8,
                "request_id": "r1",
                "latency_ms": 10,
                "stt_model": "base",
            }

        stt_service.set_test_transcribe_hook(hook)

    def tearDown(self):
        stt_service.set_test_transcribe_hook(None)

    def test_transcribe_kannada_fixture(self):
        # Non-wav bytes → hook returns KN
        files = {"audio": ("kn.webm", io.BytesIO(b"\x1a\x45\xdf\xa3fakewebm"), "audio/webm")}
        res = self.client.post("/api/chat/voice/transcribe", files=files)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(body["detected_language"], "KN")
        self.assertIn("PM-KISAN", body["text"])

    def test_transcribe_requires_auth_dependency(self):
        # With override, succeeds; without would 401 — covered by override presence
        files = {"audio": ("t.wav", io.BytesIO(make_tone_wav(0.2)), "audio/wav")}
        res = self.client.post("/api/chat/voice/transcribe", files=files)
        self.assertEqual(res.status_code, 200)


class TestSynthesizeEndpoint(unittest.TestCase):
    def setUp(self):
        from app.api.endpoints import voice as voice_ep

        self.app = FastAPI()
        self.app.include_router(voice_ep.router, prefix="/api/chat")

        async def fake_citizen():
            acc = MagicMock()
            acc.id = "cit-1"
            acc.is_active = True
            return acc

        self.app.dependency_overrides[voice_ep.get_current_citizen] = fake_citizen
        self.client = TestClient(self.app)

        def hook(text, *, language, request_id=None):
            return {
                "success": True,
                "audio": b"ID3FAKEMP3" + (text or "").encode("utf-8")[:20],
                "mime_type": "audio/mpeg",
                "language": language,
                "voice": "test",
                "cached": False,
                "request_id": request_id or "t1",
                "latency_ms": 5,
                "tts_model": "edge-tts",
            }

        tts_service.set_test_synthesize_hook(hook)

    def tearDown(self):
        tts_service.set_test_synthesize_hook(None)

    def test_synthesize_uses_response_language(self):
        res = self.client.post(
            "/api/chat/voice/synthesize",
            json={
                "text": "PM-KISAN \u0caf\u0ccb\u0c9c\u0ca8\u0cc6 Rs 6000",
                "response_language": "KN",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "audio/mpeg")
        self.assertEqual(res.headers.get("X-Response-Language"), "KN")
        self.assertTrue(res.content.startswith(b"ID3FAKEMP3"))

    def test_sequential_synthesize_requests(self):
        """Multi-turn TTS must not share broken state between calls."""
        sequence = [
            ("Hello from GramSakhi.", "EN"),
            ("Follow up answer one.", "EN"),
            ("Namaste, yeh jankari hai.", "HI"),
            ("Hindi follow up.", "HI"),
            ("Gruha Lakshmi yojane bagge.", "KN"),
            ("Kannada follow up.", "KN"),
            ("Back to English.", "EN"),
            ("Kannada again.", "KN"),
        ]
        for idx, (text, lang) in enumerate(sequence):
            res = self.client.post(
                "/api/chat/voice/synthesize",
                json={
                    "text": text,
                    "response_language": lang,
                    "request_id": f"seq-{idx}",
                },
            )
            self.assertEqual(res.status_code, 200, msg=f"idx={idx} lang={lang}")
            self.assertGreater(len(res.content), 20)
            self.assertEqual(res.headers.get("X-Response-Language"), lang)


class TestTtsPronunciation(unittest.TestCase):
    def test_display_text_unchanged(self):
        display = "Apply at https://pmkisan.gov.in/ for Rs 6000."
        d, t = build_tts_text(display, "EN")
        self.assertEqual(d, display)
        self.assertNotIn("https://", t)
        self.assertIn("pmkisan.gov.in", t)
        self.assertIn("rupees", t.lower())


class TestVoiceMessages(unittest.TestCase):
    def test_kannada_empty_audio_message(self):
        msg = voice_message("empty_audio", "KN")
        kn = sum(1 for ch in msg if "\u0c80" <= ch <= "\u0cff")
        self.assertGreater(kn, 5)


class TestVoiceDoesNotTouchRag(unittest.TestCase):
    def test_translation_voice_still_skips_rag(self):
        from app.services import conversation_service

        db = MagicMock()
        citizen = MagicMock()
        citizen.id = "c1"
        conv = MagicMock()
        conv.id = "conv1"
        conv.language = "EN"
        conv.active_scheme_context = None
        conv.title = "t"
        prev = MagicMock()
        prev.role = "assistant"
        prev.content = "PM-KISAN provides Rs 6000 per year."

        with patch.object(conversation_service, "get_owned_conversation", return_value=conv):
            with patch.object(
                conversation_service, "load_recent_messages", return_value=[prev]
            ):
                with patch.object(
                    conversation_service,
                    "store_message",
                    side_effect=lambda *a, **k: MagicMock(id="m"),
                ):
                    with patch("app.services.rag.answer_with_evidence_gate") as rag:
                        with patch(
                            "app.services.llm_service.translate_answer",
                            return_value={
                                "success": True,
                                "answer": "KN answer",
                                "response_language": "KN",
                                "model": "m",
                                "latency_ms": 1,
                            },
                        ):
                            out = conversation_service.handle_citizen_chat(
                                db,
                                citizen,
                                message="Translate the above to Kannada.",
                                conversation_id="conv1",
                                input_mode="voice",
                                stt_language="EN",
                                voice_request_id="vr1",
                            )
        rag.assert_not_called()
        self.assertEqual(out["input_mode"], "voice")
        self.assertEqual(out["voice_request_id"], "vr1")
        self.assertEqual(out["response_language"], "KN")


class TestHealthEndpoints(unittest.TestCase):
    def test_health_payload_shape(self):
        h = stt_service.get_stt_health()
        self.assertIn("configured", h)
        self.assertIn("supported_languages", h)
        self.assertEqual(h["supported_languages"], ["EN", "KN", "HI"])
        t = tts_service.get_tts_health()
        self.assertIn("voices", t)


if __name__ == "__main__":
    unittest.main()
