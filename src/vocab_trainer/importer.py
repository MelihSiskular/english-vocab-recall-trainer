from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .database import Database
from .text import clean_cell, normalize_answer

REQUIRED_COLUMNS = [
    "İngilizce Kelime",
    "Anlamı-1",
    "Cümle-1",
    "Anlamı-2",
    "Cümle-2",
    "Anlamı-3",
    "Cümle-3",
]


@dataclass(frozen=True)
class ImportSummary:
    imported: int
    updated: int
    skipped: int
    issue_count: int


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _add_issue(
    issues: list[tuple[str, int, str, str, str, str]],
    source_file: str,
    row_number: int,
    word: str,
    issue_type: str,
    details: str,
) -> None:
    issues.append((source_file, row_number, word, issue_type, details, utc_now()))


def import_vocabulary(csv_path: str | Path, database: Database) -> ImportSummary:
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV bulunamadı: {path}")

    database.initialize()
    source_file = path.name
    issues: list[tuple[str, int, str, str, str, str]] = []
    imported = 0
    updated = 0
    skipped = 0
    seen_words: set[str] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file, delimiter=";")
        missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"Eksik CSV sütunları: {', '.join(missing)}")

        rows = list(reader)

    with database.connect() as connection:
        # Keep only the latest audit result for this source file.
        connection.execute("DELETE FROM data_quality_issues WHERE source_file = ?", (source_file,))

        for row_number, row in enumerate(rows, start=2):
            raw_word = row.get("İngilizce Kelime", "")
            word = clean_cell(raw_word)
            normalized_word = normalize_answer(word)

            if raw_word != word:
                _add_issue(
                    issues,
                    source_file,
                    row_number,
                    word,
                    "whitespace_normalized",
                    "Kelimenin başındaki/sonundaki veya tekrarlanan boşluklar temizlendi.",
                )

            if not word:
                skipped += 1
                _add_issue(
                    issues,
                    source_file,
                    row_number,
                    "",
                    "missing_word",
                    "Kelime boş olduğu için satır içe aktarılmadı.",
                )
                continue

            if normalized_word in seen_words:
                skipped += 1
                _add_issue(
                    issues,
                    source_file,
                    row_number,
                    word,
                    "duplicate_word",
                    "Aynı dosyada normalize edilmiş biçimiyle tekrar eden kelime.",
                )
                continue
            seen_words.add(normalized_word)

            cleaned = {
                key: clean_cell(row.get(key, ""))
                for key in REQUIRED_COLUMNS
            }

            if not cleaned["Anlamı-1"]:
                skipped += 1
                _add_issue(
                    issues,
                    source_file,
                    row_number,
                    word,
                    "missing_primary_meaning",
                    "Anlamı-1 boş olduğu için satır içe aktarılmadı.",
                )
                continue

            for meaning_no in (2, 3):
                meaning = cleaned[f"Anlamı-{meaning_no}"]
                example = cleaned[f"Cümle-{meaning_no}"]
                if meaning and not example:
                    _add_issue(
                        issues,
                        source_file,
                        row_number,
                        word,
                        "meaning_without_example",
                        f"Anlamı-{meaning_no} var fakat Cümle-{meaning_no} boş.",
                    )
                if example and not meaning:
                    _add_issue(
                        issues,
                        source_file,
                        row_number,
                        word,
                        "example_without_meaning",
                        f"Cümle-{meaning_no} var fakat Anlamı-{meaning_no} boş.",
                    )

            for column in ("Cümle-1", "Cümle-2", "Cümle-3"):
                value = cleaned[column]
                if value.count('"') % 2 == 1:
                    _add_issue(
                        issues,
                        source_file,
                        row_number,
                        word,
                        "unbalanced_quote",
                        f"{column} alanında eşleşmeyen çift tırnak olabilir.",
                    )

            existing = connection.execute(
                "SELECT id FROM words WHERE normalized_word = ?",
                (normalized_word,),
            ).fetchone()
            now = utc_now()

            values = (
                word,
                normalized_word,
                cleaned["Anlamı-1"],
                cleaned["Cümle-1"],
                cleaned["Anlamı-2"],
                cleaned["Cümle-2"],
                cleaned["Anlamı-3"],
                cleaned["Cümle-3"],
                source_file,
                now,
            )

            if existing:
                connection.execute(
                    """
                    UPDATE words
                    SET word = ?, normalized_word = ?, meaning_1 = ?, example_1 = ?,
                        meaning_2 = ?, example_2 = ?, meaning_3 = ?, example_3 = ?,
                        source_file = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    values + (existing["id"],),
                )
                updated += 1
            else:
                connection.execute(
                    """
                    INSERT INTO words (
                        word, normalized_word, meaning_1, example_1,
                        meaning_2, example_2, meaning_3, example_3,
                        source_file, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values[:-1] + (now, now),
                )
                imported += 1

        connection.executemany(
            """
            INSERT INTO data_quality_issues (
                source_file, row_number, word, issue_type, details, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            issues,
        )

    return ImportSummary(
        imported=imported,
        updated=updated,
        skipped=skipped,
        issue_count=len(issues),
    )


def get_audit_issues(database: Database, source_file: str | None = None):
    database.initialize()
    query = """
        SELECT source_file, row_number, word, issue_type, details
        FROM data_quality_issues
    """
    params: tuple[str, ...] = ()
    if source_file:
        query += " WHERE source_file = ?"
        params = (source_file,)
    query += " ORDER BY source_file, row_number, id"

    with database.connect() as connection:
        return connection.execute(query, params).fetchall()
