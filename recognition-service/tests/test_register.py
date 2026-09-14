import os
import sys
import types
import asyncio
import unittest
from unittest.mock import patch

os.environ.setdefault("DATABASE_URL", "postgresql://user:password@localhost:5432/test")
os.environ.setdefault("RECOGNITION_API_KEYS", "test-key")

insightface_module = types.ModuleType("insightface")
insightface_app_module = types.ModuleType("insightface.app")
insightface_app_module.FaceAnalysis = object
sys.modules.setdefault("insightface", insightface_module)
sys.modules.setdefault("insightface.app", insightface_app_module)

from app.routes import register


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


class RegisterStudentTests(unittest.TestCase):
    def test_upsert_student_saves_school_id_and_external_id(self):
        cursor = FakeCursor(results=[(77, True), (1001,), (1,)])
        connection = FakeConnection(cursor)

        with patch.object(register, "get_connection", return_value=connection):
            aluno_id, external_id, created, face_samples_count = register._upsert_student(
                school_id="escola_1",
                external_id="5",
                nome="Mateus",
                vector_str="[0.1,0.2]",
            )

        self.assertEqual(aluno_id, 77)
        self.assertEqual(external_id, "5")
        self.assertTrue(created)
        self.assertEqual(face_samples_count, 1)
        self.assertEqual(cursor.queries[0][1], ("escola_1", "5", "Mateus", "[0.1,0.2]"))
        self.assertEqual(cursor.queries[1][1], (77, "[0.1,0.2]"))

    def test_manual_register_without_external_id_uses_local_id_as_fallback(self):
        cursor = FakeCursor(results=[(42,), (42,), (1001,), (1,)])
        connection = FakeConnection(cursor)

        with patch.object(register, "get_connection", return_value=connection):
            aluno_id, external_id, created, face_samples_count = register._upsert_student(
                school_id="escola_1",
                external_id=None,
                nome="Aluno Teste",
                vector_str="[0.1,0.2]",
            )

        self.assertEqual(aluno_id, 42)
        self.assertEqual(external_id, "42")
        self.assertTrue(created)
        self.assertEqual(face_samples_count, 1)
        self.assertEqual(cursor.queries[1][1], (42, "escola_1", "42", "Aluno Teste", "[0.1,0.2]"))
        self.assertEqual(cursor.queries[2][1], (42, "[0.1,0.2]"))

    def test_add_face_sample_updates_primary_embedding_and_counts_samples(self):
        cursor = FakeCursor(results=[(77,), (1002,), (3,)])
        connection = FakeConnection(cursor)

        with patch.object(register, "get_connection", return_value=connection):
            aluno_id, sample_id, face_samples_count = register._add_face_sample(
                school_id="escola_1",
                external_id="5",
                vector_str="[0.3,0.4]",
            )

        self.assertEqual(aluno_id, 77)
        self.assertEqual(sample_id, 1002)
        self.assertEqual(face_samples_count, 3)
        self.assertEqual(cursor.queries[0][1], ("[0.3,0.4]", "escola_1", "5"))
        self.assertEqual(cursor.queries[1][1], (77, "[0.3,0.4]"))

    def test_legacy_sync_maps_empresa_id_and_photo_url(self):
        captured = {}

        def fake_upsert(**kwargs):
            captured.update(kwargs)
            return 77, kwargs["external_id"], True, 1

        with patch.object(register, "_build_embedding_from_photo_url", return_value="[0.5,0.6]"), \
            patch.object(register, "_upsert_student", side_effect=fake_upsert):
            result = asyncio.run(
                register.sync_legacy_aluno(
                    {
                        "external_id": "5",
                        "nome": "Mateus",
                        "empresa_id": 1,
                        "photo_url": "https://res.cloudinary.com/demo/image/upload/aluno.jpg",
                    }
                )
            )

        self.assertEqual(captured["school_id"], "escola_1")
        self.assertEqual(captured["external_id"], "5")
        self.assertEqual(captured["nome"], "Mateus")
        self.assertEqual(captured["vector_str"], "[0.5,0.6]")
        self.assertEqual(result["face_samples_count"], 1)


if __name__ == "__main__":
    unittest.main()
