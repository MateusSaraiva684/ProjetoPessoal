import os
import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost:5432/test")
os.environ.setdefault("RECOGNITION_API_KEYS", "test-key")

insightface_module = types.ModuleType("insightface")
insightface_app_module = types.ModuleType("insightface.app")
insightface_app_module.FaceAnalysis = object
sys.modules.setdefault("insightface", insightface_module)
sys.modules.setdefault("insightface.app", insightface_app_module)

redis_module = types.ModuleType("redis")
redis_exceptions_module = types.ModuleType("redis.exceptions")
rq_module = types.ModuleType("rq")


class StubRedisError(Exception):
    pass


class StubRedis:
    @staticmethod
    def from_url(*args, **kwargs):
        raise StubRedisError("Redis stub should be patched in tests")


redis_module.Redis = StubRedis
redis_exceptions_module.RedisError = StubRedisError
rq_module.Queue = object
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.exceptions", redis_exceptions_module)
sys.modules.setdefault("rq", rq_module)

from app.routes import diagnostics


class FakeRedis:
    def ping(self):
        return True


class FakeQueue:
    name = "recognition"
    count = 3

    def __init__(self, *args, **kwargs):
        return None


class FakeCursor:
    def __init__(self, results):
        self.results = list(results)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        return None

    def fetchone(self):
        if not self.results:
            return None
        return self.results.pop(0)


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def cursor(self):
        return self.cursor_instance

    def close(self):
        return None


class DiagnosticsTests(unittest.TestCase):
    def test_diagnostics_does_not_expose_secret_values(self):
        now = datetime(2026, 5, 20, 12, tzinfo=timezone.utc)
        cursor = FakeCursor(
            results=[
                (1,),
                (10, "escola_1", "5", "entrada_principal", "Mateus", now),
                (20, "success", "escola_1", "5", "entrada_principal", True, now),
                (21, "success", "escola_1", "5", "entrada_principal", "ReadTimeout", now),
            ]
        )
        connection = FakeConnection(cursor)

        with patch.object(diagnostics.Redis, "from_url", return_value=FakeRedis()), \
            patch.object(diagnostics, "Queue", FakeQueue), \
            patch.object(diagnostics, "get_connection", return_value=connection), \
            patch.object(diagnostics, "SAAS_PRESENCE_WEBHOOK_URL", "http://saas/webhook"), \
            patch.object(diagnostics, "SCHOOL_ID", "escola_1"), \
            patch.object(diagnostics, "CAMERA_ID", "entrada_principal"):
            payload = diagnostics.build_diagnostics_payload()

        self.assertEqual(payload["database"], "ok")
        self.assertEqual(payload["redis"], "ok")
        self.assertEqual(payload["queue"]["queued_jobs"], 3)
        self.assertTrue(payload["webhook_configured"])
        serialized = repr(payload)
        self.assertNotIn("webhook-secret", serialized)
        self.assertNotIn("dev-recognition-key", serialized)
        self.assertNotIn("SAAS_WEBHOOK_SECRET", serialized)
        self.assertNotIn("RECOGNITION_API_KEYS", serialized)


if __name__ == "__main__":
    unittest.main()
