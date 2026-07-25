from datetime import datetime, timedelta, timezone
from pathlib import Path

from vocab_trainer.database import Database
from vocab_trainer.mastery import calculate_state


def _seed_word(database: Database) -> int:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with database.connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO words (
                word, normalized_word, meaning_1, source_file, created_at, updated_at
            )
            VALUES ('Appeal', 'appeal', 'Çağrı', 'test.csv', ?, ?)
            """,
            (now, now),
        )
        return cursor.lastrowid


def _add_session_attempt(
    database: Database,
    word_id: int,
    session_no: int,
    correct: bool,
    used_hint: bool = False,
    days_ago: int = 0,
):
    started = (
        datetime.now(timezone.utc) - timedelta(days=days_ago)
    ).isoformat(timespec="seconds")
    session_id = f"session-{session_no}"
    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO sessions (
                id, started_at, ended_at, status, mode, planned_words
            )
            VALUES (?, ?, ?, 'completed', 'all', 1)
            """,
            (session_id, started, started),
        )
        connection.execute(
            """
            INSERT INTO attempts (
                session_id, word_id, attempt_index, prompt_snapshot,
                answer, normalized_answer, is_correct, error_type,
                similarity, response_seconds, used_hint, created_at
            )
            VALUES (?, ?, 1, '[]', ?, ?, ?, ?, 1.0, 1.0, ?, ?)
            """,
            (
                session_id,
                word_id,
                "Appeal" if correct else "Grant",
                "appeal" if correct else "grant",
                int(correct),
                None if correct else "semantic_confusion",
                int(used_hint),
                started,
            ),
        )


def test_two_clean_first_attempts_make_word_known(tmp_path: Path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    word_id = _seed_word(database)
    _add_session_attempt(database, word_id, 1, True, days_ago=2)
    _add_session_attempt(database, word_id, 2, True, days_ago=1)

    assert calculate_state(database, word_id) == "known"


def test_hint_prevents_known_state(tmp_path: Path):
    database = Database(tmp_path / "test.db")
    database.initialize()
    word_id = _seed_word(database)
    _add_session_attempt(database, word_id, 1, True, days_ago=2)
    _add_session_attempt(database, word_id, 2, True, used_hint=True, days_ago=1)

    assert calculate_state(database, word_id) == "learning"
