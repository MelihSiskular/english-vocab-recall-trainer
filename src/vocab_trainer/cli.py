from __future__ import annotations

import argparse
from pathlib import Path

from .analytics import (
    export_attempts,
    get_hardest_words,
    get_session_progress,
    get_summary,
)
from .database import Database
from .importer import get_audit_issues, import_vocabulary
from .quiz import run_quiz

DEFAULT_DATABASE = Path("data/vocab_trainer.db")


def _database_from_args(args) -> Database:
    return Database(args.database)


def _print_summary(summary: dict[str, object]) -> None:
    print("\nGENEL DURUM")
    print("-" * 48)
    print(f"Toplam kelime          : {summary['total_words']}")
    print(f"Yeni                    : {summary['new_words']}")
    print(f"Öğreniliyor             : {summary['learning_words']}")
    print(f"Biliniyor               : {summary['known_words']}")
    print(f"Ustalaşıldı             : {summary['mastered_words']}")
    print(f"Tamamlanan çalışma      : {summary['completed_sessions']}")
    print(f"Toplam cevap            : {summary['total_attempts']}")
    print(f"Genel doğruluk          : %{summary['overall_accuracy'] * 100:.1f}")
    print(f"İlk deneme doğruluğu    : %{summary['first_try_accuracy'] * 100:.1f}")
    print(f"Ort. cevap süresi       : {summary['average_response_seconds']:.2f} sn")
    print(f"Son 7 günde yeni bilinen: {summary['newly_known_last_7_days']}")

    distribution = summary["error_distribution"]
    if distribution:
        print("\nHATA DAĞILIMI")
        print("-" * 48)
        for error_type, count in distribution.items():
            print(f"{error_type:<30} {count}")


def _print_hardest(rows: list[dict[str, object]]) -> None:
    if not rows:
        print("Henüz analiz edilecek deneme yok.")
        return
    print(
        f"{'Kelime':<24} {'Durum':<10} {'Deneme':>6} "
        f"{'Yanlış':>6} {'Hata %':>7} {'Ort.sn':>7}  En sık hata"
    )
    print("-" * 92)
    for row in rows:
        print(
            f"{str(row['word'])[:23]:<24} {row['state']:<10} "
            f"{row['attempts']:>6} {row['wrong']:>6} "
            f"{row['error_rate'] * 100:>6.1f}% "
            f"{row['avg_seconds']:>7.2f}  {row['most_common_error']}"
        )


def _print_sessions(rows: list[dict[str, object]]) -> None:
    if not rows:
        print("Henüz çalışma kaydı yok.")
        return
    print(
        f"{'Tarih':<25} {'Durum':<10} {'Mod':<10} {'Kelime':>7} "
        f"{'Cevap':>7} {'Yanlış':>7} {'İlk %':>7}"
    )
    print("-" * 88)
    for row in rows:
        print(
            f"{row['started_at'][:24]:<25} {row['status']:<10} "
            f"{row['mode']:<10} {row['studied_words']:>7} "
            f"{row['attempts']:>7} {row['wrong']:>7} "
            f"{row['first_try_accuracy'] * 100:>6.1f}%"
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vocab-trainer",
        description="CSV tabanlı İngilizce kelime hatırlama ve ilerleme takip uygulaması.",
    )
    parser.add_argument(
        "--database",
        default=str(DEFAULT_DATABASE),
        help=f"SQLite veritabanı yolu (varsayılan: {DEFAULT_DATABASE})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="Veritabanını oluştur.")

    import_parser = subparsers.add_parser("import", help="Kelime CSV dosyasını içe aktar.")
    import_parser.add_argument("csv_path", help="Noktalı virgülle ayrılmış CSV yolu.")

    audit_parser = subparsers.add_parser("audit", help="Son veri kalite raporunu göster.")
    audit_parser.add_argument("--source-file", help="Yalnızca bu dosyanın sonuçlarını göster.")

    quiz_parser = subparsers.add_parser("quiz", help="Yeni bir çalışma başlat.")
    quiz_parser.add_argument(
        "--mode",
        choices=["all", "new", "learning", "known", "mastered"],
        default="all",
    )
    quiz_parser.add_argument("--limit", type=int, help="Çalışılacak azami kelime sayısı.")
    quiz_parser.add_argument("--seed", type=int, help="Tekrarlanabilir karıştırma tohumu.")
    quiz_parser.add_argument(
        "--no-reason",
        action="store_true",
        help="Belirsiz yanlışlarda hata sebebi sorma.",
    )

    subparsers.add_parser("stats", help="Genel ilerleme özetini göster.")

    hardest_parser = subparsers.add_parser("hardest", help="En zor kelimeleri göster.")
    hardest_parser.add_argument("--limit", type=int, default=15)

    sessions_parser = subparsers.add_parser("sessions", help="Çalışma geçmişini göster.")
    sessions_parser.add_argument("--limit", type=int, default=20)

    export_parser = subparsers.add_parser("export", help="Cevap geçmişini CSV olarak dışa aktar.")
    export_parser.add_argument(
        "--output",
        default="data/exports/attempts.csv",
        help="Çıktı CSV yolu.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    database = _database_from_args(args)

    try:
        if args.command == "init":
            database.initialize()
            print(f"Veritabanı hazır: {database.path}")

        elif args.command == "import":
            summary = import_vocabulary(args.csv_path, database)
            print(
                f"İçe aktarıldı: {summary.imported}, "
                f"güncellendi: {summary.updated}, "
                f"atlanıldı: {summary.skipped}, "
                f"veri kalite uyarısı: {summary.issue_count}"
            )

        elif args.command == "audit":
            rows = get_audit_issues(database, args.source_file)
            if not rows:
                print("Veri kalite uyarısı bulunamadı.")
            for row in rows:
                print(
                    f"{row['source_file']}:{row['row_number']} | "
                    f"{row['word'] or '-'} | {row['issue_type']} | {row['details']}"
                )

        elif args.command == "quiz":
            result = run_quiz(
                database=database,
                mode=args.mode,
                limit=args.limit,
                seed=args.seed,
                ask_reason=not args.no_reason,
            )
            print("\nÇALIŞMA SONUCU")
            print("-" * 48)
            print(f"Durum          : {result.status}")
            print(f"Planlanan      : {result.planned_words}")
            print(f"Tamamlanan     : {result.completed_words}")
            print(f"Toplam cevap   : {result.total_attempts}")
            print(f"Yanlış cevap   : {result.wrong_attempts}")

        elif args.command == "stats":
            _print_summary(get_summary(database))

        elif args.command == "hardest":
            _print_hardest(get_hardest_words(database, args.limit))

        elif args.command == "sessions":
            _print_sessions(get_session_progress(database, args.limit))

        elif args.command == "export":
            output = export_attempts(database, args.output)
            print(f"Cevap geçmişi dışa aktarıldı: {output}")

    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
