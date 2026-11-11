"""Одна завершена транзакція на операцію; параметризовані запити."""

from contextlib import contextmanager
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from common.config import db_options


@contextmanager
def transaction(actor=None):
    # Контекст з’єднання підтверджує успіх або відкочує зміни при винятку разом із їхнім аудитом.
    with psycopg.connect(**db_options(), row_factory=dict_row) as connection:
        # Локальні параметри передають виконавця тригерам лише в межах цієї транзакції.
        connection.execute(
            """
            SELECT set_config('app.user_id', %s, true),
                   set_config('app.username', %s, true)
            """,
            (str(actor["user_id"]) if actor else "", actor["username"] if actor else "anonymous"),
        )
        yield connection


def log_action(connection, action, table_name, key=None, actor=None):
    connection.execute(
        """
        INSERT INTO bookstore.activity_log
            (user_id, username, action, table_name, record_key)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            actor["user_id"] if actor else None,
            actor["username"] if actor else "anonymous",
            action,
            table_name,
            Jsonb(key or {}),
        ),
    )
