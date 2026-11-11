"""Запуск: python -m console_app.main (з папки lab-4)."""

import argparse
from getpass import getpass
import json
import psycopg

from common import services
from common.catalog import ENTITIES, AccessError
from common.errors import error_text


def display(rows):
    print(json.dumps(rows, ensure_ascii=False, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Консольний клієнт книгарні")
    parser.add_argument("--check", action="store_true", help="Перевірити підключення до БД")
    args = parser.parse_args()
    if args.check:
        display(services.health())
        return
    print("\nКНИГАРНЯ · консольний застосунок\n")
    actor = services.authenticate(input("Логін: "), getpass("Пароль: "))
    if not actor:
        print("Неправильний логін або пароль.")
        return
    print(f"Вхід: {actor['username']} · {actor['role']}")
    while True:
        print(
            "\n1 Каталог / пошук\n2 Додати книгу\n3 Редагувати книгу\n4 Видалити книгу"
            "\n5 Замовлення\n6 Статистика\n0 Вийти"
        )
        action = input("Операція: ").strip()
        try:
            if action == "0":
                from common.database import transaction, log_action

                with transaction(actor) as conn:
                    log_action(conn, "LOGOUT", "app_users", actor=actor)
                break
            if action == "1":
                display(
                    services.list_entities(
                        "books", actor, q=input("Пошук (Enter - усі): "), limit=1000
                    )["rows"]
                )
            elif action in ("2", "3"):
                item_id = int(input("ID книги: ")) if action == "3" else None
                previous = services.get_entity("books", item_id, actor) if item_id else {}
                if not item_id:
                    display(services.references(actor))
                data = {}
                for name, label, _, _ in ENTITIES["books"]["fields"]:
                    value = input(
                        f"{label}" + (f" [{previous.get(name)}]" if previous else "") + ": "
                    )
                    data[name] = value if value else previous.get(name, "")
                print("Збережено, ID:", services.save_entity("books", data, actor, item_id))
            elif action == "4":
                item_id = int(input("ID книги: "))
                if input("Для підтвердження введіть DELETE: ") == "DELETE":
                    services.delete_entity("books", item_id, actor)
                    print("Запис видалено.")
            elif action == "5":
                display(services.orders(actor))
            elif action == "6":
                display(services.statistics(actor))
            else:
                print("Невідома команда.")
        except (ValueError, LookupError, AccessError, psycopg.Error) as exc:
            print("Операцію не виконано:", error_text(exc))


if __name__ == "__main__":
    try:
        main()
    except psycopg.Error as exc:
        print(error_text(exc))
        raise SystemExit(1)
