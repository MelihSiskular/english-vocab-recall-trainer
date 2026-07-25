from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .database import Database


def get_summary(database: Database) -> dict[str, object]:
    database.initialize()
    with database.connect() as connection:
        state_rows = connection.execute(
            "SELECT state, COUNT(*) AS count FROM words GROUP BY state"
        ).fetchall()
        states = {row["state"]: row["count"] for row in state_rows}

        total_attempts = connection.execute(
            "SELECT COUNT(*) AS count FROM attempts"
        ).fetchone()["count"]
        correct_attempts = connection.execute(
            "SELECT COUNT(*) AS count FROM attempts WHERE is_correct = 1"
        ).fetchone()["count"]
        completed_sessions = connection.execute(
            "SELECT COUNT(*) AS count FROM sessions WHERE status = 'completed'"
        ).fetchone()["count"]

        first_attempts = connection.execute(
            """
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(is_correct), 0) AS correct
            FROM attempts a
            JOIN sessions s ON s.id = a.session_id
            WHERE a.attempt_index = 1 AND s.status = 'completed'
            """
        ).fetchone()

        average_seconds = connection.execute(
            "SELECT AVG(response_seconds) AS value FROM attempts"
        ).fetchone()["value"]

        error_rows = connection.execute(
            """
            SELECT error_type, COUNT(*) AS count
            FROM attempts
            WHERE is_correct = 0
            GROUP BY error_type
            ORDER BY count DESC
            """
        ).fetchall()

        week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(
            timespec="seconds"
        )
        newly_known = connection.execute(
            """
            SELECT COUNT(DISTINCT word_id) AS count
            FROM word_state_history
            WHERE new_state IN ('known', 'mastered')
              AND changed_at >= ?
            """,
            (week_ago,),
        ).fetchone()["count"]

    return {
        "total_words": sum(states.values()),
        "new_words": states.get("new", 0),
        "learning_words": states.get("learning", 0),
        "known_words": states.get("known", 0),
        "mastered_words": states.get("mastered", 0),
        "completed_sessions": completed_sessions,
        "total_attempts": total_attempts,
        "overall_accuracy": (correct_attempts / total_attempts) if total_attempts else 0.0,
        "first_try_accuracy": (
            first_attempts["correct"] / first_attempts["total"]
            if first_attempts["total"]
            else 0.0
        ),
        "average_response_seconds": float(average_seconds or 0.0),
        "newly_known_last_7_days": newly_known,
        "error_distribution": {
            row["error_type"] or "unknown": row["count"] for row in error_rows
        },
    }


def get_hardest_words(database: Database, limit: int = 15) -> list[dict[str, object]]:
    database.initialize()
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT
                w.id,
                w.word,
                w.state,
                COUNT(a.id) AS attempts,
                SUM(CASE WHEN a.is_correct = 0 THEN 1 ELSE 0 END) AS wrong,
                AVG(a.response_seconds) AS avg_seconds,
                MAX(a.created_at) AS last_seen
            FROM words w
            JOIN attempts a ON a.word_id = w.id
            GROUP BY w.id, w.word, w.state
            HAVING COUNT(a.id) > 0
            ORDER BY
                (1.0 * SUM(CASE WHEN a.is_correct = 0 THEN 1 ELSE 0 END) / COUNT(a.id)) DESC,
                COUNT(a.id) DESC,
                AVG(a.response_seconds) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

        output = []
        for row in rows:
            errors = connection.execute(
                """
                SELECT error_type
                FROM attempts
                WHERE word_id = ? AND is_correct = 0 AND error_type IS NOT NULL
                """,
                (row["id"],),
            ).fetchall()
            most_common_error = (
                Counter(error["error_type"] for error in errors).most_common(1)[0][0]
                if errors
                else "-"
            )
            attempts = row["attempts"]
            wrong = row["wrong"]
            output.append(
                {
                    "word": row["word"],
                    "state": row["state"],
                    "attempts": attempts,
                    "wrong": wrong,
                    "error_rate": wrong / attempts if attempts else 0.0,
                    "avg_seconds": float(row["avg_seconds"] or 0.0),
                    "most_common_error": most_common_error,
                    "last_seen": row["last_seen"],
                }
            )
    return output


def get_session_progress(database: Database, limit: int = 20) -> list[dict[str, object]]:
    database.initialize()
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT
                s.id,
                s.started_at,
                s.status,
                s.mode,
                s.planned_words,
                COUNT(a.id) AS attempts,
                COUNT(DISTINCT a.word_id) AS studied_words,
                SUM(CASE WHEN a.is_correct = 0 THEN 1 ELSE 0 END) AS wrong,
                SUM(CASE WHEN a.attempt_index = 1 THEN 1 ELSE 0 END) AS first_total,
                SUM(CASE WHEN a.attempt_index = 1 AND a.is_correct = 1 THEN 1 ELSE 0 END) AS first_correct
            FROM sessions s
            LEFT JOIN attempts a ON a.session_id = s.id
            GROUP BY s.id
            ORDER BY s.started_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    result = []
    for row in rows:
        first_total = row["first_total"] or 0
        result.append(
            {
                "session_id": row["id"],
                "started_at": row["started_at"],
                "status": row["status"],
                "mode": row["mode"],
                "planned_words": row["planned_words"],
                "studied_words": row["studied_words"],
                "attempts": row["attempts"],
                "wrong": row["wrong"] or 0,
                "first_try_accuracy": (
                    (row["first_correct"] or 0) / first_total if first_total else 0.0
                ),
            }
        )
    return result


def export_attempts(database: Database, output_path: str | Path) -> Path:
    database.initialize()
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT
                a.id AS attempt_id,
                a.session_id,
                s.started_at AS session_started_at,
                s.status AS session_status,
                w.word,
                w.state AS current_state,
                a.attempt_index,
                a.answer,
                a.is_correct,
                a.error_type,
                a.confused_with_word,
                a.similarity,
                a.response_seconds,
                a.used_hint,
                a.created_at
            FROM attempts a
            JOIN words w ON w.id = a.word_id
            JOIN sessions s ON s.id = a.session_id
            ORDER BY a.created_at, a.id
            """
        ).fetchall()

    fieldnames = [
        "attempt_id",
        "session_id",
        "session_started_at",
        "session_status",
        "word",
        "current_state",
        "attempt_index",
        "answer",
        "is_correct",
        "error_type",
        "confused_with_word",
        "similarity",
        "response_seconds",
        "used_hint",
        "created_at",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return path
