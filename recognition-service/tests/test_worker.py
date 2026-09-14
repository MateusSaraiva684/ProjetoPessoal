import os
import sys
import types
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost:5432/test")
os.environ.setdefault("RECOGNITION_API_KEYS", "test-key")

redis_module = types.ModuleType("redis")
redis_exceptions_module = types.ModuleType("redis.exceptions")


class StubRedisError(Exception):
    pass


class StubRedis:
    @staticmethod
    def from_url(*args, **kwargs):
        raise StubRedisError("Redis stub should be patched in tests")


redis_module.Redis = StubRedis
redis_exceptions_module.RedisError = StubRedisError
sys.modules.setdefault("redis", redis_module)
sys.modules.setdefault("redis.exceptions", redis_exceptions_module)

insightface_module = types.ModuleType("insightface")
insightface_app_module = types.ModuleType("insightface.app")
insightface_app_module.FaceAnalysis = object
sys.modules.setdefault("insightface", insightface_module)
sys.modules.setdefault("insightface.app", insightface_app_module)

from app.queue import worker


class FakeEmbedding:
    def tolist(self):
        return [0.1] * 512


class FakeCursor:
    def __init__(self, match_row=None, match_rows=None, insert_row=None):
        self.match_rows = match_rows if match_rows is not None else ([match_row] if match_row else [])
        self.insert_row = insert_row
        self.queries = []
        self._next_result = None
        self._next_results = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.queries.append((sql, params))
        if "FROM embeddings" in sql:
            self._next_results = self.match_rows
        elif "INSERT INTO presencas" in sql:
            self._next_result = self.insert_row

    def fetchone(self):
        return self._next_result

    def fetchall(self):
        return self._next_results


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


class WorkerRecognitionTests(unittest.TestCase):
    def test_process_recognition_sends_external_id_instead_of_local_id(self):
        cursor = FakeCursor(
            match_row=(99, "escola_1", "5", "Mateus", 1001, 0.1),
            insert_row=(123, datetime(2026, 5, 20, 10, 15, tzinfo=timezone.utc)),
        )
        connection = FakeConnection(cursor)
        webhook_calls = []

        with patch.object(worker, "get_embedding", return_value=FakeEmbedding()), \
            patch.object(worker, "get_connection", return_value=connection), \
            patch("app.services.audit.get_connection", return_value=connection), \
            patch.object(worker, "_claim_presence_dedup", return_value=True), \
            patch.object(worker, "CAMERA_ID", "entrada_principal"), \
            patch.object(worker, "SCHOOL_ID", "escola_1"), \
            patch.object(worker, "send_presence_event", side_effect=lambda **kwargs: webhook_calls.append(kwargs) or True):
            result = worker.process_recognition(b"image")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["aluno_id"], 99)
        self.assertEqual(result["school_id"], "escola_1")
        self.assertEqual(result["student_id"], "5")
        self.assertEqual(result["face_sample_id"], 1001)
        self.assertEqual(webhook_calls[0]["school_id"], "escola_1")
        self.assertEqual(webhook_calls[0]["student_id"], "5")

        select_query = [query for query in cursor.queries if "FROM embeddings" in query[0]][0]
        self.assertEqual(select_query[1][1], "escola_1")
        insert_query = [query for query in cursor.queries if "INSERT INTO presencas" in query[0]][0]
        self.assertEqual(insert_query[1], (99, "escola_1", "5", "entrada_principal", "Mateus"))
        event_query = [query for query in cursor.queries if "INSERT INTO recognition_events" in query[0]][0]
        self.assertEqual(event_query[1][0], "success")
        self.assertEqual(event_query[1][2], "5")
        self.assertEqual(event_query[1][5], 1001)
        self.assertEqual(event_query[1][8], 123)
        self.assertTrue(event_query[1][10])

    def test_process_recognition_duplicate_skips_presence_and_webhook(self):
        cursor = FakeCursor(match_row=(99, "escola_1", "5", "Mateus", 1001, 0.1))
        connection = FakeConnection(cursor)

        with patch.object(worker, "get_embedding", return_value=FakeEmbedding()), \
            patch.object(worker, "get_connection", return_value=connection), \
            patch.object(worker, "_claim_presence_dedup", return_value=False), \
            patch.object(worker, "CAMERA_ID", "entrada_principal"), \
            patch.object(worker, "SCHOOL_ID", "escola_1"), \
            patch.object(worker, "send_presence_event") as send_presence_event:
            result = worker.process_recognition(b"image")

        self.assertEqual(result["status"], "duplicate")
        self.assertEqual(result["student_id"], "5")
        self.assertEqual(result["message"], "Presenca ja registrada recentemente")
        self.assertFalse(any("INSERT INTO presencas" in query[0] for query in cursor.queries))
        event_query = [query for query in cursor.queries if "INSERT INTO recognition_events" in query[0]][0]
        self.assertEqual(event_query[1][0], "duplicate")
        self.assertEqual(event_query[1][2], "5")
        send_presence_event.assert_not_called()

    def test_process_recognition_ambiguous_match_skips_presence_and_webhook(self):
        cursor = FakeCursor(
            match_rows=[
                (99, "escola_1", "5", "Mateus", 1001, 0.1),
                (100, "escola_1", "6", "Mateus Duplicado", 1002, 0.105),
            ]
        )
        connection = FakeConnection(cursor)

        with patch.object(worker, "get_embedding", return_value=FakeEmbedding()), \
            patch.object(worker, "get_connection", return_value=connection), \
            patch.object(worker, "MATCH_AMBIGUITY_MARGIN", 0.02), \
            patch.object(worker, "CAMERA_ID", "entrada_principal"), \
            patch.object(worker, "SCHOOL_ID", "escola_1"), \
            patch.object(worker, "send_presence_event") as send_presence_event:
            result = worker.process_recognition(b"image")

        self.assertEqual(result["status"], "ambiguous_match")
        self.assertEqual(result["student_id"], "5")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertFalse(any("INSERT INTO presencas" in query[0] for query in cursor.queries))
        event_query = [query for query in cursor.queries if "INSERT INTO recognition_events" in query[0]][0]
        self.assertEqual(event_query[1][0], "ambiguous_match")
        self.assertEqual(event_query[1][2], "5")
        send_presence_event.assert_not_called()

    def test_process_recognition_no_match_records_event(self):
        cursor = FakeCursor(match_row=(99, "escola_1", "5", "Mateus", 1001, 0.9))
        connection = FakeConnection(cursor)

        with patch.object(worker, "get_embedding", return_value=FakeEmbedding()), \
            patch.object(worker, "get_connection", return_value=connection), \
            patch.object(worker, "SIMILARITY_THRESHOLD", 0.75), \
            patch.object(worker, "CAMERA_ID", "entrada_principal"), \
            patch.object(worker, "SCHOOL_ID", "escola_1"), \
            patch.object(worker, "send_presence_event") as send_presence_event:
            result = worker.process_recognition(b"image")

        self.assertEqual(result["status"], "no_match")
        event_query = [query for query in cursor.queries if "INSERT INTO recognition_events" in query[0]][0]
        self.assertEqual(event_query[1][0], "no_match")
        self.assertEqual(event_query[1][7], 0.9)
        self.assertFalse(any("INSERT INTO presencas" in query[0] for query in cursor.queries))
        send_presence_event.assert_not_called()

    def test_process_identification_returns_match_without_presence_or_webhook(self):
        cursor = FakeCursor(match_row=(99, "escola_1", "5", "Mateus", 1001, 0.1))
        connection = FakeConnection(cursor)

        with patch.object(worker, "get_embedding", return_value=FakeEmbedding()), \
            patch.object(worker, "get_connection", return_value=connection), \
            patch.object(worker, "CAMERA_ID", "entrada_principal"), \
            patch.object(worker, "SCHOOL_ID", "escola_1"), \
            patch.object(worker, "send_presence_event") as send_presence_event:
            result = worker.process_identification(b"image")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["student_id"], "5")
        self.assertEqual(result["external_id"], "5")
        self.assertEqual(result["saas_aluno_id"], 5)
        self.assertFalse(any("INSERT INTO presencas" in query[0] for query in cursor.queries))
        event_query = [query for query in cursor.queries if "INSERT INTO recognition_events" in query[0]][0]
        self.assertEqual(event_query[1][0], "success")
        send_presence_event.assert_not_called()

    def test_dedup_window_allows_new_claim_after_expiration(self):
        class FakeRedis:
            now = 0
            store = {}

            def set(self, key, value, *, nx, ex):
                expires_at = self.store.get(key)
                if nx and expires_at is not None and expires_at > self.now:
                    return None
                self.store[key] = self.now + ex
                return True

        fake_redis = FakeRedis()

        with patch.object(worker, "PRESENCE_DEDUP_WINDOW_SECONDS", 300), \
            patch.object(worker.Redis, "from_url", return_value=fake_redis):
            first = worker._claim_presence_dedup(
                school_id="escola_1",
                camera_id="entrada_principal",
                external_id="5",
            )
            second = worker._claim_presence_dedup(
                school_id="escola_1",
                camera_id="entrada_principal",
                external_id="5",
            )
            fake_redis.now = 301
            third = worker._claim_presence_dedup(
                school_id="escola_1",
                camera_id="entrada_principal",
                external_id="5",
            )

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertTrue(third)


if __name__ == "__main__":
    unittest.main()
