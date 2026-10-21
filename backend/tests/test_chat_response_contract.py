"""Regression: chat API response includes fields the web client maps in onComplete."""

import unittest

from app.schemas.chat import ChatResponse


class ChatResponseContractTests(unittest.TestCase):
    def test_payload_includes_frontend_mapped_fields(self):
        payload = ChatResponse(
            answer="Gruha Lakshmi is a Karnataka scheme.",
            conversation_id="00000000-0000-0000-0000-000000000001",
            assistant_message_id="00000000-0000-0000-0000-000000000002",
            original_query="Tell me about Gruha Lakshmi.",
            response_language="EN",
            validated=True,
            sources=[],
        )
        dumped = payload.model_dump()
        self.assertEqual(dumped["answer"], "Gruha Lakshmi is a Karnataka scheme.")
        self.assertEqual(
            dumped["conversation_id"], "00000000-0000-0000-0000-000000000001"
        )
        self.assertEqual(
            dumped["assistant_message_id"], "00000000-0000-0000-0000-000000000002"
        )
        self.assertEqual(dumped["response_language"], "EN")


if __name__ == "__main__":
    unittest.main()
