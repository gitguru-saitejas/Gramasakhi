"""Cloud runtime profile and embedding provider tests."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.core.config import settings
from app.services.ivr.ivr_config import collect_ivr_production_config_errors
from app.services.runtime_profile import (
    cloud_config_errors,
    is_cloud_runtime,
    should_warm_cross_encoder_at_startup,
)


class TestCloudRuntime(unittest.TestCase):
    def test_cloud_requires_gemini_llm_and_embeddings(self):
        with patch.object(settings, "RUNTIME_PROFILE", "cloud"):
            with patch.object(settings, "LLM_PROVIDER", "ollama"):
                with patch.object(settings, "EMBEDDING_PROVIDER", "ollama"):
                    with patch.object(settings, "GEMINI_API_KEY", ""):
                        with patch.object(settings, "LLM_FALLBACK_TO_OLLAMA", True):
                            errors = cloud_config_errors()
        self.assertTrue(any("LLM_PROVIDER" in e for e in errors))
        self.assertTrue(any("EMBEDDING_PROVIDER" in e for e in errors))
        self.assertTrue(any("GEMINI_API_KEY" in e for e in errors))
        self.assertTrue(any("FALLBACK" in e for e in errors))

    def test_cloud_config_ok_when_aligned(self):
        with patch.object(settings, "RUNTIME_PROFILE", "cloud"):
            with patch.object(settings, "APP_ENV", "production"):
                with patch.object(settings, "LLM_PROVIDER", "gemini"):
                    with patch.object(settings, "EMBEDDING_PROVIDER", "gemini"):
                        with patch.object(settings, "GEMINI_API_KEY", "test-key"):
                            with patch.object(settings, "LLM_FALLBACK_TO_OLLAMA", False):
                                with patch.object(settings, "OTP_DELIVERY_MODE", "sms"):
                                    with patch.object(settings, "OTP_DEV_POPUP_ENABLED", False):
                                        self.assertEqual(cloud_config_errors(), [])

    def test_gemini_embed_routing_mocked(self):
        with patch("app.services.gemini_embedding.embed_text", return_value=[0.1] * 768):
            with patch.object(settings, "EMBEDDING_PROVIDER", "gemini"):
                from app.services.rag import get_embeddings

                vec = get_embeddings("PM-KISAN benefits")
        self.assertEqual(len(vec), 768)

    def test_ivr_production_skipped_when_mock(self):
        with patch.object(settings, "APP_ENV", "production"):
            with patch.object(settings, "IVR_PROVIDER", "mock"):
                with patch.object(settings, "IVR_PUBLIC_BASE_URL", ""):
                    self.assertEqual(collect_ivr_production_config_errors(settings), [])

    def test_ivr_production_validates_when_exotel(self):
        fake = type(
            "S",
            (),
            {
                "APP_ENV": "production",
                "IVR_PROVIDER": "exotel",
                "IVR_PUBLIC_BASE_URL": "https://api.example.in",
                "IVR_CITIZEN_ACCOUNT_ID": "id-1",
                "IVR_SYSTEM_ACCOUNT_PHONE": "",
                "OTP_DEV_RETRIEVAL_ENABLED": False,
                "OTP_CONSOLE_SIMULATOR_ENABLED": False,
                "DATABASE_URL": "postgresql://x",
                "IVR_WEBHOOK_SHARED_SECRET": "",
            },
        )()
        errors = collect_ivr_production_config_errors(fake)
        self.assertTrue(any("IVR_WEBHOOK_SHARED_SECRET" in e for e in errors))

    def test_startup_cross_encoder_warmup_disabled_flag(self):
        with patch.object(settings, "HYBRID_RERANK_ENABLED", True):
            with patch.object(settings, "STARTUP_WARM_CROSS_ENCODER", False):
                self.assertFalse(should_warm_cross_encoder_at_startup())
        with patch.object(settings, "HYBRID_RERANK_ENABLED", True):
            with patch.object(settings, "STARTUP_WARM_CROSS_ENCODER", True):
                self.assertTrue(should_warm_cross_encoder_at_startup())


if __name__ == "__main__":
    unittest.main()
