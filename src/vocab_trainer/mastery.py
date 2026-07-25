from __future__ import annotations

from datetime import datetime

from .database import Database


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def calculate_state(database: Database, word_id: int) -> str:
    """
    Transparent mastery model:

    new:
        No completed-session attempt.
    learning:
        Seen, but recall is not yet stable.
    known:
        First attempt is correct without a hint in the last 2 completed sessions.
    mastered:
        Same condition in the last 4 completed sessions and those sessions span
        at least 7 days.
    """
    with database.connect() as connection:
        rows = connection.execute(
            """
            SELECT
                s.id AS session_id,
                s.started_at,
                MIN(a.attempt_index) AS first_attempt_index,
                (
                    SELECT a2.is_correct
                    FROM attempts a2
                    WHERE a2.session_id = s.id AND a2.word_id = ?
                    ORDER BY a2.attempt_index ASC, a2.id ASC
                    LIMIT 1
                ) AS first_correct,
                (
                    SELECT a2.used_hint
                    FROM attempts a2
                    WHERE a2.session_id = s.id AND a2.word_id = ?
                    ORDER BY a2.attempt_index ASC, a2.id ASC
                    LIMIT 1
                ) AS first_used_hint
            FROM sessions s
            JOIN attempts a ON a.session_id = s.id
            WHERE s.status = 'completed' AND a.word_id = ?
            GROUP BY s.id, s.started_at
            ORDER BY s.started_at ASC
            """,
            (word_id, word_id, word_id),
        ).fetchall()

    if not rows:
        return "new"

    first_results = [
        bool(row["first_correct"]) and not bool(row["first_used_hint"])
        for row in rows
    ]

    if len(rows) >= 4 and all(first_results[-4:]):
        first_date = _parse_datetime(rows[-4]["started_at"])
        last_date = _parse_datetime(rows[-1]["started_at"])
        if (last_date - first_date).days >= 7:
            return "mastered"

    if len(rows) >= 2 and all(first_results[-2:]):
        return "known"

    return "learning"


def update_states_for_session(database: Database, session_id: str) -> None:
    with database.connect() as connection:
        word_ids = [
            row["word_id"]
            for row in connection.execute(
                "SELECT DISTINCT word_id FROM attempts WHERE session_id = ?",
                (session_id,),
            ).fetchall()
        ]

    for word_id in word_ids:
        new_state = calculate_state(database, word_id)
        with database.connect() as connection:
            row = connection.execute(
                "SELECT state FROM words WHERE id = ?",
                (word_id,),
            ).fetchone()
            if not row:
                continue
            old_state = row["state"]
            if old_state == new_state:
                continue

            changed_at = connection.execute(
                "SELECT COALESCE(ended_at, started_at) AS changed_at FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()["changed_at"]

            connection.execute(
                "UPDATE words SET state = ?, updated_at = ? WHERE id = ?",
                (new_state, changed_at, word_id),
            )
            connection.execute(
                """
                INSERT INTO word_state_history (
                    word_id, session_id, old_state, new_state, changed_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (word_id, session_id, old_state, new_state, changed_at),
            )
