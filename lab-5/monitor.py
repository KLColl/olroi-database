"""Періодичний моніторинг індексів і повільних запитів PostgreSQL."""

import argparse
from datetime import datetime
from getpass import getpass
import os
import textwrap
import time

import psycopg
from psycopg.rows import dict_row


INDEX_STATISTICS = """
    SELECT
        schemaname,
        relname AS table_name,
        indexrelname AS index_name,
        idx_scan,
        idx_tup_read,
        idx_tup_fetch,
        pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
    FROM pg_stat_user_indexes
    WHERE schemaname IN ('bookstore', 'lab5')
    ORDER BY idx_scan DESC, schemaname, relname, indexrelname
"""

SLOW_QUERIES = """
    SELECT
        queryid,
        calls,
        ROUND(mean_exec_time::NUMERIC, 3) AS mean_ms,
        ROUND(total_exec_time::NUMERIC, 3) AS total_ms,
        ROUND(max_exec_time::NUMERIC, 3) AS max_ms,
        query
    FROM public.pg_stat_statements
    WHERE dbid = (SELECT oid FROM pg_database WHERE datname = current_database())
      AND query NOT ILIKE '%pg_stat_statements%'
    ORDER BY mean_exec_time DESC, calls DESC
    LIMIT 10
"""


def print_snapshot(connection, sample_number):
    print(f"\nЗнімок {sample_number} | {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("\nВикористання індексів")
    print("Індекс | сканувань | прочитано | отримано | розмір")

    for row in connection.execute(INDEX_STATISTICS).fetchall():
        print(
            f"{row['schemaname']}.{row['index_name']} | "
            f"{row['idx_scan']} | {row['idx_tup_read']} | "
            f"{row['idx_tup_fetch']} | {row['index_size']}"
        )

    print("\nНайповільніші запити за середнім часом")
    for row in connection.execute(SLOW_QUERIES).fetchall():
        print(
            f"queryid={row['queryid']} | викликів={row['calls']} | "
            f"середній={row['mean_ms']} мс | загальний={row['total_ms']} мс | "
            f"максимальний={row['max_ms']} мс"
        )
        query = " ".join(row["query"].split())
        print(textwrap.shorten(query, width=150, placeholder="..."))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--user", default="postgres")
    parser.add_argument("--database", default="bookstore_lab5")
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--interval", type=float, default=5)
    args = parser.parse_args()

    if args.samples < 1 or args.interval < 0:
        parser.error("Кількість знімків має бути додатною, інтервал невід’ємним.")

    password = os.getenv("PGPASSWORD") or getpass("Пароль PostgreSQL: ")
    with psycopg.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        dbname=args.database,
        password=password,
        connect_timeout=5,
        autocommit=True,
        options="-c default_transaction_read_only=on",
        row_factory=dict_row,
    ) as connection:
        print(f"База даних {args.database} | користувач {args.user}")
        for number in range(1, args.samples + 1):
            print_snapshot(connection, number)
            if number < args.samples:
                time.sleep(args.interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nМоніторинг зупинено.")
    except psycopg.Error as exc:
        raise SystemExit(f"Помилка PostgreSQL: {exc}") from None
