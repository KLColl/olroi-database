"""Розгортання SQL лише в порожній БД; наявна схема ніколи не очищується."""

from pathlib import Path
import argparse
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import psycopg
from common.config import ROOT, db_options


def initialize(demo=False):
    with psycopg.connect(**db_options(), autocommit=True) as conn:
        if conn.execute("SELECT to_regnamespace('bookstore')").fetchone()[0]:
            raise RuntimeError(
                "Схема bookstore вже існує. Повторне розгортання відхилено; дані не змінено."
            )
        for path in sorted((ROOT / "database").glob("[0-9][0-9]_*.sql")):
            conn.execute(path.read_text(encoding="utf-8"))
            print("OK:", path.name)
        if demo:
            for path in sorted((ROOT / "database" / "fixtures").glob("*.sql")):
                conn.execute(path.read_text(encoding="utf-8"))
                print("DEMO:", path.name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Розгортання схеми в порожній БД")
    parser.add_argument(
        "--demo", action="store_true", help="Додати навчальні дані та облікові записи"
    )
    initialize(demo=parser.parse_args().demo)
