import asyncio
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost:5432/test")
os.environ.setdefault("RECOGNITION_API_KEYS", "test-key")

from app.routes import operations


class FakeCursor:
    def __init__(self, results):
        self.results = list(results)
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.queries.append((sql, params))

    def fetchone(self):
        if not self.results:
            return None
        return self.results.pop(0)

    def fetchall(self):
        if not self.results:
            return []
        return self.results.pop(0)


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_instance = cursor

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        return None


class OperationsTests(unittest.TestCase):
    def test_list_face_samples_does_not_return_embeddings(self):
        now = datetime(2026, 5, 20, 12, tzinfo=timezone.utc)
        cursor = FakeCursor(
            results=[
                (77, "escola_1", "5", "Mateus", None),
                [(1002, now), (1001, now)],
            ]
        )
        connection = FakeConnection(cursor)

        with patch.object(operations, "get_connection", return_value=connection):
            result = asyncio.run(
                operations.list_student_face_samples(school_id="escola_1", external_id="5")
            )

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["ids"], [1002, 1001])
        self.assertNotIn("embedding", result["samples"][0])

    def test_delete_face_sample_requires_confirmation_and_updates_primary_embedding(self):
        cursor = FakeCursor(
            results=[
                (77, "escola_1", "5", "Mateus", None),
                (1002,),
                ("[0.2,0.3]",),
                (1,),
            ]
        )
        connection = FakeConnection(cursor)

        with patch.object(operations, "get_connection", return_value=connection), \
            patch.object(operations, "CAMERA_ID", "entrada_principal"):
            result = asyncio.run(
                operations.delete_student_face_sample(
                    face_sample_id=1002,
                    school_id="escola_1",
                    external_id="5",
                    confirm_external_id="5",
                )
            )

        self.assertEqual(result["deleted_face_sample_id"], 1002)
        self.assertEqual(result["remaining_face_samples"], 1)
        self.assertTrue(any("DELETE FROM embeddings" in query[0] for query in cursor.queries))
        event_query = [query for query in cursor.queries if "INSERT INTO recognition_events" in query[0]][0]
        self.assertEqual(event_query[1][0], "biometric_sample_deleted")
        self.assertEqual(event_query[1][5], 1002)

    def test_archive_duplicate_student_marks_only_duplicate(self):
        archived_at = datetime(2026, 5, 20, 12, tzinfo=timezone.utc)
        cursor = FakeCursor(
            results=[
                (77, "escola_1", "5", "Mateus", None),
                (78, "escola_1", "6", "Mateus", None),
                (archived_at,),
            ]
        )
        connection = FakeConnection(cursor)

        with patch.object(operations, "get_connection", return_value=connection), \
            patch.object(operations, "CAMERA_ID", "entrada_principal"):
            result = asyncio.run(
                operations.archive_duplicate_student(
                    school_id="escola_1",
                    correct_external_id="5",
                    duplicate_external_id="6",
                    confirmation="archive:escola_1:5:6",
                )
            )

        self.assertEqual(result["correct_external_id"], "5")
        self.assertEqual(result["archived_duplicate_external_id"], "6")
        update_query = [query for query in cursor.queries if "UPDATE alunos" in query[0]][0]
        self.assertEqual(update_query[1][1], "5")
        self.assertEqual(update_query[1][2], 78)


if __name__ == "__main__":
    unittest.main()
