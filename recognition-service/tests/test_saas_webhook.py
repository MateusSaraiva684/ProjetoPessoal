import hashlib
import hmac
import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost:5432/test")
os.environ.setdefault("RECOGNITION_API_KEYS", "test-key")

from app.services import saas_webhook


class SaasWebhookTests(unittest.TestCase):
    def test_send_presence_event_signs_raw_json_and_uses_idempotency_key(self):
        calls = []

        class FakeResponse:
            def raise_for_status(self):
                return None

        def fake_post(url, *, data, headers, timeout):
            calls.append({"url": url, "data": data, "headers": headers, "timeout": timeout})
            return FakeResponse()

        with patch.object(saas_webhook, "SAAS_PRESENCE_WEBHOOK_URL", "http://saas/api/recognition/presences"), \
            patch.object(saas_webhook, "SAAS_WEBHOOK_SECRET", "webhook-secret"), \
            patch.object(saas_webhook, "SAAS_WEBHOOK_TIMEOUT_SECONDS", 2), \
            patch.object(saas_webhook, "CAMERA_ID", "entrada_principal"), \
            patch.object(saas_webhook.requests, "post", side_effect=fake_post):
            sent = saas_webhook.send_presence_event(
                presence_id=123,
                school_id="escola_1",
                student_id="5",
                student_name="Mateus",
                confidence=0.91,
                detected_at=datetime(2026, 5, 20, 10, 15, tzinfo=timezone.utc),
            )

        self.assertTrue(sent)
        self.assertTrue(sent.sent)
        self.assertEqual(sent.event_id, "presence:escola_1:123")
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(call["headers"]["Idempotency-Key"], "presence:escola_1:123")

        expected_digest = hmac.new(
            b"webhook-secret",
            call["data"],
            hashlib.sha256,
        ).hexdigest()
        self.assertEqual(call["headers"]["X-Recognition-Signature"], f"sha256={expected_digest}")

        payload = json.loads(call["data"].decode("utf-8"))
        self.assertEqual(payload["event_id"], "presence:escola_1:123")
        self.assertEqual(payload["school_id"], "escola_1")
        self.assertEqual(payload["student_id"], "5")
        self.assertEqual(payload["student_name"], "Mateus")

    def test_send_presence_event_without_url_does_not_raise_or_post(self):
        with patch.object(saas_webhook, "SAAS_PRESENCE_WEBHOOK_URL", ""), \
            patch.object(saas_webhook.requests, "post") as post:
            sent = saas_webhook.send_presence_event(
                presence_id=1,
                school_id="escola_1",
                student_id="5",
                student_name="Mateus",
                confidence=0.9,
                detected_at=datetime.now(timezone.utc),
            )

        self.assertFalse(sent)
        self.assertEqual(sent.error, "webhook_url_not_configured")
        post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
