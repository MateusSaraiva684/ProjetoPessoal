import logging
from difflib import SequenceMatcher
from typing import Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status

from app.core.config import CAMERA_ID
from app.core.database import get_connection
from app.core.security import require_api_key
from app.services.audit import fetch_recent_ambiguous_events, record_recognition_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["operations"], dependencies=[Depends(require_api_key)])


def _normalize(value: str | None, field_name: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name}_required",
        )
    return normalized


def _name_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, " ".join(left.lower().split()), " ".join(right.lower().split())).ratio()


def _fetch_student(cur, *, school_id: str, external_id: str) -> tuple[int, str, str, str, Any] | None:
    cur.execute(
        """
        SELECT id, school_id, external_id, nome, archived_at
        FROM alunos
        WHERE school_id = %s AND external_id = %s
        """,
        (school_id, external_id),
    )
    return cur.fetchone()


def _latest_remaining_embedding(cur, aluno_id: int) -> str | None:
    cur.execute(
        """
        SELECT embedding
        FROM embeddings
        WHERE aluno_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (aluno_id,),
    )
    result = cur.fetchone()
    return result[0] if result else None


def _update_primary_embedding(cur, aluno_id: int) -> None:
    cur.execute(
        "UPDATE alunos SET embedding = %s WHERE id = %s",
        (_latest_remaining_embedding(cur, aluno_id), aluno_id),
    )


@router.get("/students/faces")
async def list_student_face_samples(
    school_id: str = Query(...),
    external_id: str = Query(...),
) -> dict[str, Any]:
    normalized_school_id = _normalize(school_id, "school_id")
    normalized_external_id = _normalize(external_id, "external_id")

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            student = _fetch_student(
                cur,
                school_id=normalized_school_id,
                external_id=normalized_external_id,
            )
            if not student:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="student_not_found")

            aluno_id, _, _, nome, archived_at = student
            cur.execute(
                """
                SELECT id, created_at
                FROM embeddings
                WHERE aluno_id = %s
                ORDER BY created_at DESC, id DESC
                """,
                (aluno_id,),
            )
            samples = [
                {"id": row[0], "created_at": row[1].isoformat() if row[1] else None}
                for row in cur.fetchall()
            ]
            return {
                "school_id": normalized_school_id,
                "external_id": normalized_external_id,
                "nome": nome,
                "archived": archived_at is not None,
                "count": len(samples),
                "ids": [sample["id"] for sample in samples],
                "samples": samples,
            }
    finally:
        conn.close()


@router.delete("/students/faces/{face_sample_id}")
async def delete_student_face_sample(
    face_sample_id: int,
    school_id: str = Query(...),
    external_id: str = Query(...),
    confirm_external_id: str = Query(...),
) -> dict[str, Any]:
    normalized_school_id = _normalize(school_id, "school_id")
    normalized_external_id = _normalize(external_id, "external_id")
    confirmation = _normalize(confirm_external_id, "confirm_external_id")
    if confirmation != normalized_external_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="confirmation_mismatch")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                student = _fetch_student(
                    cur,
                    school_id=normalized_school_id,
                    external_id=normalized_external_id,
                )
                if not student:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="student_not_found")

                aluno_id = student[0]
                cur.execute(
                    """
                    DELETE FROM embeddings
                    WHERE id = %s AND aluno_id = %s
                    RETURNING id
                    """,
                    (face_sample_id, aluno_id),
                )
                deleted = cur.fetchone()
                if not deleted:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="face_sample_not_found")

                _update_primary_embedding(cur, aluno_id)
                cur.execute("SELECT COUNT(*) FROM embeddings WHERE aluno_id = %s", (aluno_id,))
                remaining = cur.fetchone()[0]
                record_recognition_event(
                    status="biometric_sample_deleted",
                    school_id=normalized_school_id,
                    external_id=normalized_external_id,
                    camera_id=CAMERA_ID,
                    aluno_id=aluno_id,
                    face_sample_id=face_sample_id,
                    metadata={"remaining_face_samples": remaining},
                    cur=cur,
                )

        return {
            "status": "ok",
            "deleted_face_sample_id": face_sample_id,
            "school_id": normalized_school_id,
            "external_id": normalized_external_id,
            "remaining_face_samples": remaining,
        }
    finally:
        conn.close()


@router.delete("/students/faces")
async def delete_all_student_face_samples(
    school_id: str = Query(...),
    external_id: str = Query(...),
    confirm_external_id: str = Query(...),
    remove_student: bool = Query(False),
) -> dict[str, Any]:
    normalized_school_id = _normalize(school_id, "school_id")
    normalized_external_id = _normalize(external_id, "external_id")
    confirmation = _normalize(confirm_external_id, "confirm_external_id")
    if confirmation != normalized_external_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="confirmation_mismatch")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                student = _fetch_student(
                    cur,
                    school_id=normalized_school_id,
                    external_id=normalized_external_id,
                )
                if not student:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="student_not_found")

                aluno_id = student[0]
                cur.execute("SELECT id FROM embeddings WHERE aluno_id = %s", (aluno_id,))
                sample_ids = [row[0] for row in cur.fetchall()]
                cur.execute("DELETE FROM embeddings WHERE aluno_id = %s", (aluno_id,))
                cur.execute("UPDATE alunos SET embedding = NULL WHERE id = %s", (aluno_id,))

                student_removed = False
                if remove_student:
                    cur.execute("SELECT COUNT(*) FROM presencas WHERE aluno_id = %s", (aluno_id,))
                    presence_count = cur.fetchone()[0]
                    if presence_count > 0:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="student_has_presence_history",
                        )
                    cur.execute("DELETE FROM alunos WHERE id = %s", (aluno_id,))
                    student_removed = True

                record_recognition_event(
                    status="biometrics_deleted",
                    school_id=normalized_school_id,
                    external_id=normalized_external_id,
                    camera_id=CAMERA_ID,
                    aluno_id=None if student_removed else aluno_id,
                    metadata={
                        "deleted_face_sample_ids": sample_ids,
                        "student_removed": student_removed,
                    },
                    cur=cur,
                )

        return {
            "status": "ok",
            "school_id": normalized_school_id,
            "external_id": normalized_external_id,
            "deleted_face_samples": len(sample_ids),
            "student_removed": student_removed,
        }
    finally:
        conn.close()


@router.get("/students/duplicates")
async def list_possible_duplicates(
    school_id: str = Query(...),
    embedding_distance_threshold: float = Query(0.08, ge=0),
    name_similarity_threshold: float = Query(0.88, ge=0, le=1),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    normalized_school_id = _normalize(school_id, "school_id")
    pairs: dict[tuple[str, str], dict[str, Any]] = {}

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    a1.id,
                    a1.external_id,
                    a1.nome,
                    e1.id AS sample_id_1,
                    a2.id,
                    a2.external_id,
                    a2.nome,
                    e2.id AS sample_id_2,
                    e1.embedding <-> e2.embedding AS distance
                FROM embeddings e1
                JOIN alunos a1 ON a1.id = e1.aluno_id
                JOIN embeddings e2 ON e1.id < e2.id
                JOIN alunos a2 ON a2.id = e2.aluno_id
                WHERE a1.school_id = %s
                  AND a2.school_id = a1.school_id
                  AND a1.external_id <> a2.external_id
                  AND a1.archived_at IS NULL
                  AND a2.archived_at IS NULL
                  AND (e1.embedding <-> e2.embedding) <= %s
                ORDER BY distance ASC
                LIMIT %s
                """,
                (normalized_school_id, embedding_distance_threshold, limit),
            )
            for row in cur.fetchall():
                key = tuple(sorted((row[1], row[5])))
                pairs[key] = {
                    "school_id": normalized_school_id,
                    "student_a": {
                        "aluno_id": row[0],
                        "external_id": row[1],
                        "nome": row[2],
                        "face_sample_id": row[3],
                    },
                    "student_b": {
                        "aluno_id": row[4],
                        "external_id": row[5],
                        "nome": row[6],
                        "face_sample_id": row[7],
                    },
                    "embedding_distance": float(row[8]),
                    "name_similarity": _name_similarity(row[2], row[6]),
                    "reasons": ["embedding_close"],
                }

            cur.execute(
                """
                SELECT id, external_id, nome
                FROM alunos
                WHERE school_id = %s
                  AND archived_at IS NULL
                ORDER BY id
                LIMIT %s
                """,
                (normalized_school_id, limit),
            )
            students = cur.fetchall()
            for index, left in enumerate(students):
                for right in students[index + 1 :]:
                    if left[1] == right[1]:
                        continue
                    similarity = _name_similarity(left[2], right[2])
                    if similarity < name_similarity_threshold:
                        continue
                    key = tuple(sorted((left[1], right[1])))
                    pair = pairs.setdefault(
                        key,
                        {
                            "school_id": normalized_school_id,
                            "student_a": {"aluno_id": left[0], "external_id": left[1], "nome": left[2]},
                            "student_b": {"aluno_id": right[0], "external_id": right[1], "nome": right[2]},
                            "embedding_distance": None,
                            "name_similarity": similarity,
                            "reasons": [],
                        },
                    )
                    pair["name_similarity"] = max(pair.get("name_similarity") or 0, similarity)
                    if "name_similar" not in pair["reasons"]:
                        pair["reasons"].append("name_similar")

        return {
            "school_id": normalized_school_id,
            "count": len(pairs),
            "duplicates": list(pairs.values()),
        }
    finally:
        conn.close()


@router.post("/students/duplicates/archive")
async def archive_duplicate_student(
    school_id: str = Form(...),
    correct_external_id: str = Form(...),
    duplicate_external_id: str = Form(...),
    confirmation: str = Form(...),
    reason: str = Form("duplicate_student"),
) -> dict[str, Any]:
    normalized_school_id = _normalize(school_id, "school_id")
    correct_id = _normalize(correct_external_id, "correct_external_id")
    duplicate_id = _normalize(duplicate_external_id, "duplicate_external_id")
    if correct_id == duplicate_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="same_external_id")
    if confirmation != f"archive:{normalized_school_id}:{correct_id}:{duplicate_id}":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="confirmation_mismatch")

    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                correct = _fetch_student(cur, school_id=normalized_school_id, external_id=correct_id)
                duplicate = _fetch_student(cur, school_id=normalized_school_id, external_id=duplicate_id)
                if not correct or not duplicate:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="student_not_found")
                if correct[4] is not None:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="correct_student_archived")
                if duplicate[4] is not None:
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="duplicate_already_archived")

                duplicate_aluno_id = duplicate[0]
                cur.execute(
                    """
                    UPDATE alunos
                    SET
                        archived_at = now(),
                        archive_reason = %s,
                        merged_into_external_id = %s
                    WHERE id = %s
                    RETURNING archived_at
                    """,
                    (reason, correct_id, duplicate_aluno_id),
                )
                archived_at = cur.fetchone()[0]
                record_recognition_event(
                    status="duplicate_archived",
                    school_id=normalized_school_id,
                    external_id=duplicate_id,
                    camera_id=CAMERA_ID,
                    aluno_id=duplicate_aluno_id,
                    metadata={
                        "correct_external_id": correct_id,
                        "duplicate_external_id": duplicate_id,
                        "reason": reason,
                    },
                    cur=cur,
                )

        return {
            "status": "ok",
            "school_id": normalized_school_id,
            "correct_external_id": correct_id,
            "archived_duplicate_external_id": duplicate_id,
            "archived_at": archived_at.isoformat(),
        }
    finally:
        conn.close()


@router.get("/recognition-events/ambiguous")
async def list_recent_ambiguous_matches(limit: int = Query(50, ge=1, le=200)) -> dict[str, Any]:
    events = fetch_recent_ambiguous_events(limit=limit)
    return {"count": len(events), "events": events}
