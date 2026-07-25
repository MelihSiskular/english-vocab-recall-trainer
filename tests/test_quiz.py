from pathlib import Path

from vocab_trainer.database import Database
from vocab_trainer.importer import import_vocabulary
from vocab_trainer.quiz import run_quiz


def test_wrong_word_reappears_and_attempts_are_persisted(tmp_path: Path):
    csv_path = tmp_path / "words.csv"
    csv_path.write_text(
        "İngilizce Kelime;Anlamı-1;Cümle-1;Anlamı-2;Cümle-2;Anlamı-3;Cümle-3\n"
        "Appeal;Çağrı;Their appeal was accepted;;;;\n",
        encoding="utf-8",
    )
    database = Database(tmp_path / "test.db")
    import_vocabulary(csv_path, database)
    answers = iter(["grant", "appeal"])

    result = run_quiz(
        database,
        mode="all",
        seed=1,
        ask_reason=False,
        input_fn=lambda _: next(answers),
    )

    assert result.status == "completed"
    assert result.completed_words == 1
    assert result.total_attempts == 2
    assert result.wrong_attempts == 1

    with database.connect() as connection:
        rows = connection.execute(
            "SELECT attempt_index, is_correct FROM attempts ORDER BY id"
        ).fetchall()
        state = connection.execute("SELECT state FROM words").fetchone()["state"]

    assert [(row["attempt_index"], row["is_correct"]) for row in rows] == [(1, 0), (2, 1)]
    assert state == "learning"
