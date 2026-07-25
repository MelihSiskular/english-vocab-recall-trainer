from pathlib import Path

from vocab_trainer.database import Database
from vocab_trainer.importer import import_vocabulary


def test_importer_loads_semicolon_csv_and_normalizes_word(tmp_path: Path):
    csv_path = tmp_path / "words.csv"
    csv_path.write_text(
        "İngilizce Kelime;Anlamı-1;Cümle-1;Anlamı-2;Cümle-2;Anlamı-3;Cümle-3\n"
        " Reflect ;Yansıtmak;The result reflects change;;;;\n",
        encoding="utf-8",
    )
    database = Database(tmp_path / "test.db")

    summary = import_vocabulary(csv_path, database)

    assert summary.imported == 1
    assert summary.issue_count == 1
    with database.connect() as connection:
        row = connection.execute("SELECT word, normalized_word FROM words").fetchone()
    assert row["word"] == "Reflect"
    assert row["normalized_word"] == "reflect"


def test_reimport_updates_without_losing_word_state(tmp_path: Path):
    csv_path = tmp_path / "words.csv"
    header = "İngilizce Kelime;Anlamı-1;Cümle-1;Anlamı-2;Cümle-2;Anlamı-3;Cümle-3\n"
    csv_path.write_text(header + "Appeal;Çağrı;Example;;;;\n", encoding="utf-8")
    database = Database(tmp_path / "test.db")
    import_vocabulary(csv_path, database)

    with database.connect() as connection:
        connection.execute("UPDATE words SET state = 'known' WHERE normalized_word = 'appeal'")

    csv_path.write_text(header + "Appeal;Güçlü çağrı;New example;;;;\n", encoding="utf-8")
    summary = import_vocabulary(csv_path, database)

    assert summary.updated == 1
    with database.connect() as connection:
        row = connection.execute(
            "SELECT meaning_1, state FROM words WHERE normalized_word = 'appeal'"
        ).fetchone()
    assert row["meaning_1"] == "Güçlü çağrı"
    assert row["state"] == "known"
