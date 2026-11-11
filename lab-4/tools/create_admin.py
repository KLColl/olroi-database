"""Створення першого адміністратора оператором із доступом до PostgreSQL."""

from getpass import getpass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg
from common.catalog import ValidationError, validate_registration
from common.database import transaction
from common.errors import error_text
from common.security import hash_password


def main():
    username = input("Логін адміністратора: ")
    email = input("Email адміністратора: ")
    password = getpass("Пароль: ")
    if password != getpass("Підтвердження пароля: "):
        raise ValidationError("Паролі не збігаються.")
    username, email = validate_registration(username, email, password)
    encoded = hash_password(password)
    with transaction() as conn:
        conn.execute("LOCK TABLE bookstore.app_users IN SHARE ROW EXCLUSIVE MODE")
        if conn.execute(
            "SELECT 1 FROM bookstore.app_users WHERE role='admin' AND is_active LIMIT 1"
        ).fetchone():
            raise ValidationError(
                "Активний адміністратор уже існує. Керування ролями доступне у вебінтерфейсі."
            )
        conn.execute("SELECT set_config('app.username','bootstrap',true)")
        conn.execute(
            """
            INSERT INTO bookstore.app_users (username, email, password_hash, role)
            VALUES (%s, %s, %s, 'admin')
            """,
            (username, email, encoded),
        )
    print("Адміністратора створено.")


if __name__ == "__main__":
    try:
        main()
    except (ValidationError, psycopg.Error) as exc:
        print(error_text(exc))
        raise SystemExit(1)
