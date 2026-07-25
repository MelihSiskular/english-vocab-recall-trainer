from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS words (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    normalized_word TEXT NOT NULL UNIQUE,
    meaning_1 TEXT NOT NULL,
    example_1 TEXT NOT NULL DEFAULT '',
    meaning_2 TEXT NOT NULL DEFAULT '',
    example_2 TEXT NOT NULL DEFAULT '',
    meaning_3 TEXT NOT NULL DEFAULT '',
    example_3 TEXT NOT NULL DEFAULT '',
    state TEXT NOT NULL DEFAULT 'new'
        CHECK (state IN ('new', 'learning', 'known', 'mastered')),
    source_file TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL
        CHECK (status IN ('running', 'completed', 'aborted')),
    mode TEXT NOT NULL,
    planned_words INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    word_id INTEGER NOT NULL,
    attempt_index INTEGER NOT NULL,
    prompt_snapshot TEXT NOT NULL,
    answer TEXT NOT NULL,
    normalized_answer TEXT NOT NULL,
    is_correct INTEGER NOT NULL CHECK (is_correct IN (0, 1)),
    error_type TEXT,
    confused_with_word TEXT,
    similarity REAL NOT NULL,
    response_seconds REAL NOT NULL,
    used_hint INTEGER NOT NULL DEFAULT 0 CHECK (used_hint IN (0, 1)),
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id),
    FOREIGN KEY (word_id) REFERENCES words(id)
);

CREATE INDEX IF NOT EXISTS idx_attempts_word_id ON attempts(word_id);
CREATE INDEX IF NOT EXISTS idx_attempts_session_id ON attempts(session_id);
CREATE INDEX IF NOT EXISTS idx_attempts_created_at ON attempts(created_at);

CREATE TABLE IF NOT EXISTS word_state_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word_id INTEGER NOT NULL,
    session_id TEXT,
    old_state TEXT NOT NULL,
    new_state TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    FOREIGN KEY (word_id) REFERENCES words(id),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE IF NOT EXISTS data_quality_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT NOT NULL,
    row_number INTEGER NOT NULL,
    word TEXT NOT NULL DEFAULT '',
    issue_type TEXT NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
