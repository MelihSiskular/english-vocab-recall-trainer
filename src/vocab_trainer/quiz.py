from __future__ import annotations

import json
import random
import time
import uuid
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from .database import Database
from .mastery import update_states_for_session
from .text import (
    classify_wrong_answer,
    normalize_answer,
    redact_target,
    similarity,
)

RETRY_GAP = 3


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class QuizResult:
    session_id: str
    status: str
    planned_words: int
    completed_words: int
    total_attempts: int
    wrong_attempts: int


def _prompt_snapshot(word) -> str:
    meanings = [
        word["meaning_1"],
        word["meaning_2"],
        word["meaning_3"],
    ]
    return json.dumps(
        [meaning for meaning in meanings if meaning],
        ensure_ascii=False,
    )


def _ask_uncertain_reason(input_fn: Callable[[str], str]) -> str:
    print(
        "\nHata sebebini seç: "
        "[1] Hatırlayamadım  "
        "[2] Başka kelimeyle karıştırdım  "
        "[3] Anlamı yanlış yorumladım  "
        "[Enter] Diğer"
    )
    choice = input_fn("> ").strip()
    return {
        "1": "recall_failure",
        "2": "semantic_confusion",
        "3": "meaning_misinterpreted",
    }.get(choice, "other")


def _insert_with_gap(queue: deque, word, gap: int = RETRY_GAP) -> None:
    items = list(queue)
    index = min(gap, len(items))
    items.insert(index, word)
    queue.clear()
    queue.extend(items)


def run_quiz(
    database: Database,
    mode: str = "all",
    limit: int | None = None,
    seed: int | None = None,
    ask_reason: bool = True,
    input_fn: Callable[[str], str] = input,
) -> QuizResult:
    database.initialize()
    valid_modes = {"all", "new", "learning", "known", "mastered"}
    if mode not in valid_modes:
        raise ValueError(f"Geçersiz mod: {mode}. Seçenekler: {', '.join(sorted(valid_modes))}")

    with database.connect() as connection:
        all_rows = connection.execute(
            "SELECT * FROM words ORDER BY word COLLATE NOCASE"
        ).fetchall()
        if mode == "all":
            rows = all_rows
        else:
            rows = [row for row in all_rows if row["state"] == mode]

    words = list(rows)
    randomizer = random.Random(seed)
    randomizer.shuffle(words)
    if limit is not None:
        words = words[: max(0, limit)]

    if not words:
        raise ValueError("Bu seçim için çalışılacak kelime bulunamadı.")

    vocabulary_map = {row["normalized_word"]: row["word"] for row in all_rows}
    session_id = str(uuid.uuid4())
    started_at = utc_now()

    with database.connect() as connection:
        connection.execute(
            """
            INSERT INTO sessions (id, started_at, status, mode, planned_words)
            VALUES (?, ?, 'running', ?, ?)
            """,
            (session_id, started_at, mode, len(words)),
        )

    queue = deque(words)
    completed_word_ids: set[int] = set()
    attempt_counts: dict[int, int] = {}
    total_attempts = 0
    wrong_attempts = 0
    aborted = False

    print("\nKomutlar: :hint = örnek cümle, :q = çalışmayı bitir")
    print("Yanlış cevaplanan kelime birkaç soru sonra tekrar gelir.\n")

    while queue:
        word = queue.popleft()
        if word["id"] in completed_word_ids:
            continue

        attempt_counts[word["id"]] = attempt_counts.get(word["id"], 0) + 1
        attempt_index = attempt_counts[word["id"]]
        used_hint = False

        print("=" * 68)
        print(f"İlerleme: {len(completed_word_ids)}/{len(words)}")
        print(f"Anlam 1: {word['meaning_1']}")
        if word["meaning_2"]:
            print(f"Anlam 2: {word['meaning_2']}")
        if word["meaning_3"]:
            print(f"Anlam 3: {word['meaning_3']}")

        started_answering = time.perf_counter()
        while True:
            answer = input_fn("\nKelime: ")
            if answer.strip().casefold() == ":q":
                aborted = True
                break
            if answer.strip().casefold() == ":hint":
                used_hint = True
                examples = [
                    word["example_1"],
                    word["example_2"],
                    word["example_3"],
                ]
                visible_examples = [
                    redact_target(example, word["word"])
                    for example in examples
                    if example
                ]
                if visible_examples:
                    for index, example in enumerate(visible_examples, start=1):
                        print(f"İpucu {index}: {example}")
                else:
                    print("Bu kelime için örnek cümle bulunmuyor.")
                continue
            break

        if aborted:
            break

        response_seconds = round(time.perf_counter() - started_answering, 3)
        normalized = normalize_answer(answer)
        is_correct = normalized == word["normalized_word"]
        score = similarity(answer, word["word"])
        error_type = None
        confused_with_word = None

        if is_correct:
            print("✓ Doğru")
            completed_word_ids.add(word["id"])
        else:
            wrong_attempts += 1
            error_type, score, confused_with_word = classify_wrong_answer(
                answer=answer,
                target=word["word"],
                vocabulary_by_normalized_word=vocabulary_map,
            )
            if error_type == "unclassified_wrong_answer" and ask_reason:
                error_type = _ask_uncertain_reason(input_fn)

            print(f"✗ Yanlış. Doğru cevap: {word['word']}")
            if confused_with_word:
                print(f"Karıştırılan kelime: {confused_with_word}")
            print(f"Kaydedilen hata türü: {error_type}")
            _insert_with_gap(queue, word)

        total_attempts += 1
        with database.connect() as connection:
            connection.execute(
                """
                INSERT INTO attempts (
                    session_id, word_id, attempt_index, prompt_snapshot,
                    answer, normalized_answer, is_correct, error_type,
                    confused_with_word, similarity, response_seconds,
                    used_hint, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    word["id"],
                    attempt_index,
                    _prompt_snapshot(word),
                    answer,
                    normalized,
                    int(is_correct),
                    error_type,
                    confused_with_word,
                    score,
                    response_seconds,
                    int(used_hint),
                    utc_now(),
                ),
            )

    ended_at = utc_now()
    status = "aborted" if aborted else "completed"
    with database.connect() as connection:
        connection.execute(
            "UPDATE sessions SET ended_at = ?, status = ? WHERE id = ?",
            (ended_at, status, session_id),
        )

    if status == "completed":
        update_states_for_session(database, session_id)

    return QuizResult(
        session_id=session_id,
        status=status,
        planned_words=len(words),
        completed_words=len(completed_word_ids),
        total_attempts=total_attempts,
        wrong_attempts=wrong_attempts,
    )
