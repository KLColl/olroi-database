"""Єдина бізнес-логіка для FastAPI, HTML та консольного клієнта."""

from datetime import datetime
from decimal import Decimal
import hashlib
from pathlib import Path
import os
import secrets
import shutil
import subprocess

from psycopg import sql

from common.catalog import (
    ENTITIES,
    ValidationError,
    require_admin,
    require_editor,
    validate_entity,
    validate_registration,
)
from common.config import ROOT, db_options
from common.database import log_action, transaction
from common.security import hash_password, verify_password

PUBLIC_USER = "user_id, username, email, role, is_active, created_at"


def get_user(user_id=None, token=None):
    if not user_id and not token:
        return None
    with transaction() as conn:
        if token:
            return conn.execute(
                f"""
                SELECT {PUBLIC_USER}
                FROM bookstore.app_users
                WHERE api_token_hash = %s AND is_active
                """,
                (hashlib.sha256(token.encode()).hexdigest(),),
            ).fetchone()
        return conn.execute(
            f"""
            SELECT {PUBLIC_USER}
            FROM bookstore.app_users
            WHERE user_id = %s AND is_active
            """,
            (user_id,),
        ).fetchone()


def authenticate(username, password):
    if len(password) > 128:
        return None
    with transaction() as conn:
        user = conn.execute(
            "SELECT * FROM bookstore.app_users WHERE username=%s", (username.strip().lower(),)
        ).fetchone()
        valid = user and user["is_active"] and verify_password(password, user["password_hash"])
        actor = {k: user[k] for k in ("user_id", "username", "role")} if valid else None
        log_action(conn, "LOGIN", "app_users", {"success": bool(valid)}, actor)
        if not valid:
            return None
        return {k: v for k, v in user.items() if k not in ("password_hash", "api_token_hash")}


def register(username, email, password):
    username, email = validate_registration(username, email, password)
    encoded = hash_password(password)
    with transaction() as conn:
        user_id = conn.execute(
            """
            INSERT INTO bookstore.app_users (username, email, password_hash, role)
            VALUES (%s, %s, %s, 'reader')
            RETURNING user_id
            """,
            (username, email, encoded),
        ).fetchone()["user_id"]
        log_action(conn, "REGISTER", "app_users", {"user_id": user_id})
        return user_id


def issue_api_token(actor):
    token = secrets.token_urlsafe(32)
    # Заміна хешу анулює попередній токен; відкритий токен повертається лише під час створення.
    with transaction(actor) as conn:
        conn.execute(
            "UPDATE bookstore.app_users SET api_token_hash=%s WHERE user_id=%s",
            (hashlib.sha256(token.encode()).hexdigest(), actor["user_id"]),
        )
    return token


def references(actor):
    with transaction(actor) as conn:
        return dict(
            authors=conn.execute("""
            SELECT author_id AS id, first_name || ' ' || last_name AS name
            FROM bookstore.authors
            ORDER BY last_name, first_name
            """).fetchall(),
            categories=conn.execute("""
            SELECT category_id AS id, category_name AS name
            FROM bookstore.categories
            ORDER BY category_name
            """).fetchall(),
            customers=conn.execute("""
            SELECT customer_id AS id, full_name AS name
            FROM bookstore.customers
            ORDER BY full_name
            """).fetchall(),
        )


def list_entities(
    entity,
    actor,
    q="",
    sort="",
    direction="asc",
    page=1,
    category="",
    min_price="",
    max_price="",
    limit=20,
):
    if entity not in ENTITIES:
        raise LookupError("Сторінку не знайдено.")
    conf = ENTITIES[entity]
    page, limit = max(1, int(page)), min(1000, max(1, int(limit)))
    if len(q) > 200:
        raise ValidationError("Пошуковий запит: не більше 200 символів.")
    source = "book_catalog" if entity == "books" else entity
    allowed = [f[0] for f in conf["fields"]] + [conf["key"]]
    if entity == "books":
        allowed += ["author_name", "category_name"]
    sort = sort if sort in allowed else conf["key"]
    direction = "DESC" if direction.lower() == "desc" else "ASC"
    search_fields = (
        ["title", "isbn", "author_name", "category_name"]
        if entity == "books"
        else [f[0] for f in conf["fields"] if f[2] in ("text", "email", "phone")]
    )
    conditions, params = [], []
    if q:
        conditions.append("(" + " OR ".join(f"{col} ILIKE %s" for col in search_fields) + ")")
        params += ["%" + q + "%"] * len(search_fields)
    if entity == "books":
        if category:
            try:
                category_id = int(category)
            except (ValueError, TypeError):
                raise ValidationError("Некоректна категорія.")
            conditions.append("category_id=%s")
            params.append(category_id)
        for value, op in ((min_price, ">="), (max_price, "<=")):
            if value != "" and value is not None:
                try:
                    price = Decimal(str(value).replace(",", "."))
                    if not price.is_finite() or price < 0:
                        raise ValueError
                except (ValueError, ArithmeticError):
                    raise ValidationError("Некоректна ціна фільтра.")
                conditions.append(f"price {op} %s")
                params.append(price)
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    # Назви таблиць і полів беруться з дозволеного переліку, значення фільтрів - із параметрів.
    with transaction(actor) as conn:
        total = conn.execute(
            f"SELECT count(*) AS n FROM bookstore.{source}{where}", params
        ).fetchone()["n"]
        rows = conn.execute(
            f"""
            SELECT * FROM bookstore.{source}{where}
            ORDER BY {sort} {direction}, {conf["key"]} ASC
            LIMIT %s OFFSET %s
            """,
            params + [limit, (page - 1) * limit],
        ).fetchall()
        log_action(conn, "READ", entity, {"q": q, "page": page}, actor)
    return dict(
        rows=rows,
        total=total,
        page=page,
        pages=max(1, (total + limit - 1) // limit),
        sort=sort,
        direction=direction.lower(),
    )


def get_entity(entity, item_id, actor):
    conf = ENTITIES.get(entity)
    if not conf:
        raise LookupError("Невідома сутність.")
    with transaction(actor) as conn:
        row = conn.execute(
            f'SELECT * FROM bookstore.{entity} WHERE {conf["key"]}=%s', (item_id,)
        ).fetchone()
        if not row:
            raise LookupError("Запис не знайдено.")
        log_action(conn, "READ", entity, {conf["key"]: item_id}, actor)
        return row


def save_entity(entity, data, actor, item_id=None):
    require_editor(actor)
    values = validate_entity(entity, data)
    conf = ENTITIES[entity]
    with transaction(actor) as conn:
        if item_id is None:
            query = sql.SQL("""
            INSERT INTO bookstore.{} ({})
            VALUES ({})
            RETURNING {}
            """).format(
                sql.Identifier(entity),
                sql.SQL(",").join(map(sql.Identifier, values)),
                sql.SQL(",").join(sql.Placeholder() for _ in values),
                sql.Identifier(conf["key"]),
            )
            row = conn.execute(query, list(values.values())).fetchone()
        else:
            query = sql.SQL("""
            UPDATE bookstore.{}
            SET {}
            WHERE {} = %s
            RETURNING {}
            """).format(
                sql.Identifier(entity),
                sql.SQL(",").join(sql.SQL("{}=%s").format(sql.Identifier(k)) for k in values),
                sql.Identifier(conf["key"]),
                sql.Identifier(conf["key"]),
            )
            row = conn.execute(query, list(values.values()) + [item_id]).fetchone()
        if not row:
            raise LookupError("Запис не знайдено.")
        return row[conf["key"]]


def delete_entity(entity, item_id, actor):
    require_admin(actor)
    conf = ENTITIES.get(entity)
    if not conf:
        raise LookupError("Невідома сутність.")
    with transaction(actor) as conn:
        row = conn.execute(
            f"""
            DELETE FROM bookstore.{entity}
            WHERE {conf["key"]} = %s
            RETURNING {conf["key"]}
            """,
            (item_id,),
        ).fetchone()
        if not row:
            raise LookupError("Запис не знайдено.")


def orders(actor, status=""):
    if status and status not in ("Draft", "Confirmed", "Cancelled"):
        raise ValidationError("Невідомий статус замовлення.")
    with transaction(actor) as conn:
        rows = conn.execute(
            """
            SELECT * FROM bookstore.order_summary
            """ + ("WHERE status=%s " if status else "") + "ORDER BY order_id DESC",
            (status,) if status else (),
        ).fetchall()
        log_action(conn, "READ", "orders", {"status": status}, actor)
        return rows


def order_detail(order_id, actor):
    with transaction(actor) as conn:
        order = conn.execute(
            "SELECT * FROM bookstore.order_summary WHERE order_id=%s", (order_id,)
        ).fetchone()
        if not order:
            raise LookupError("Замовлення не знайдено.")
        items = conn.execute(
            """
            SELECT oi.*, b.title, oi.quantity * oi.unit_price AS line_total
            FROM bookstore.order_items oi
            JOIN bookstore.books b USING (book_id)
            WHERE order_id = %s
            ORDER BY b.title
            """,
            (order_id,),
        ).fetchall()
        log_action(conn, "READ", "orders", {"order_id": order_id}, actor)
        return order, items


def create_order(customer_id, actor):
    require_editor(actor)
    with transaction(actor) as conn:
        return conn.execute(
            """
            INSERT INTO bookstore.orders (customer_id)
            VALUES (%s)
            RETURNING order_id
            """,
            (int(customer_id),),
        ).fetchone()["order_id"]


def order_action(order_id, action, actor, book_id=None, quantity=None, customer_id=None):
    require_editor(actor)
    with transaction(actor) as conn:
        if action == "confirm":
            conn.execute("CALL bookstore.confirm_order(%s)", (order_id,))
        elif action == "cancel":
            conn.execute("CALL bookstore.cancel_order(%s)", (order_id,))
        elif action == "item":
            conn.execute(
                "CALL bookstore.set_order_item(%s,%s,%s)", (order_id, int(book_id), int(quantity))
            )
        elif action in ("remove_item", "delete", "customer"):
            row = conn.execute(
                """
                SELECT status FROM bookstore.orders
                WHERE order_id = %s
                FOR UPDATE
                """,
                (order_id,),
            ).fetchone()
            if not row:
                raise LookupError("Замовлення не знайдено.")
            if row["status"] != "Draft":
                raise ValidationError("Редагувати й видаляти можна лише чернетку.")
            if action == "remove_item":
                conn.execute(
                    "DELETE FROM bookstore.order_items WHERE order_id=%s AND book_id=%s",
                    (order_id, int(book_id)),
                )
            elif action == "delete":
                require_admin(actor)
                conn.execute("DELETE FROM bookstore.orders WHERE order_id=%s", (order_id,))
            else:
                conn.execute(
                    "UPDATE bookstore.orders SET customer_id=%s WHERE order_id=%s",
                    (int(customer_id), order_id),
                )
        else:
            raise ValidationError("Невідома операція.")


def statistics(actor):
    with transaction(actor) as conn:
        totals = conn.execute("""
        SELECT count(*) FILTER (WHERE status = 'Confirmed') AS sales,
               COALESCE(sum(order_total) FILTER (WHERE status = 'Confirmed'), 0) AS revenue,
               count(*) FILTER (WHERE status = 'Draft') AS drafts
        FROM bookstore.order_summary
        """).fetchone()
        totals.update(conn.execute("""
        SELECT count(*) AS titles, COALESCE(sum(stock_quantity), 0) AS stock
        FROM bookstore.books
        """).fetchone())
        categories = conn.execute("""
        SELECT c.category_name,
               COALESCE(sum(oi.quantity * oi.unit_price)
                   FILTER (WHERE o.status = 'Confirmed'), 0) AS revenue
        FROM bookstore.categories c
        LEFT JOIN bookstore.books b USING (category_id)
        LEFT JOIN bookstore.order_items oi USING (book_id)
        LEFT JOIN bookstore.orders o USING (order_id)
        GROUP BY c.category_id, c.category_name
        ORDER BY revenue DESC, c.category_name
        """).fetchall()
        daily = conn.execute("""
        WITH days AS (
            SELECT day::date AS day
            FROM generate_series(current_date - 13, current_date, interval '1 day') day
        ), sales AS (
            SELECT confirmed_at::date AS day, sum(order_total) AS revenue
            FROM bookstore.order_summary
            WHERE status = 'Confirmed'
            GROUP BY 1
        )
        SELECT d.day, COALESCE(s.revenue, 0) AS revenue
        FROM days d
        LEFT JOIN sales s USING (day)
        ORDER BY d.day
        """).fetchall()
        customers = conn.execute("""
        SELECT c.full_name,
               count(s.order_id) FILTER (WHERE s.status = 'Confirmed') AS orders,
               COALESCE(sum(s.order_total) FILTER (WHERE s.status = 'Confirmed'), 0) AS spent
        FROM bookstore.customers c
        LEFT JOIN bookstore.order_summary s USING (customer_id)
        GROUP BY c.customer_id, c.full_name
        ORDER BY spent DESC, c.full_name
        LIMIT 10
        """).fetchall()
        log_action(conn, "READ", "statistics", actor=actor)
        return dict(totals=totals, categories=categories, daily=daily, customers=customers)


def audit_log(actor, action="", q="", page=1):
    require_admin(actor)
    page = max(1, int(page))
    where, params = [], []
    if action:
        where.append("action=%s")
        params.append(action)
    if q:
        where.append("(username ILIKE %s OR table_name ILIKE %s)")
        params += ["%" + q + "%"] * 2
    clause = " WHERE " + " AND ".join(where) if where else ""
    with transaction(actor) as conn:
        count = conn.execute(
            "SELECT count(*) AS n FROM bookstore.activity_log" + clause, params
        ).fetchone()["n"]
        rows = conn.execute(
            "SELECT * FROM bookstore.activity_log" + clause + """
                            ORDER BY log_id DESC
                            LIMIT 30 OFFSET %s
                            """,
            params + [(page - 1) * 30],
        ).fetchall()
        log_action(conn, "READ", "activity_log", {"page": page}, actor)
    return dict(rows=rows, total=count, page=page, pages=max(1, (count + 29) // 30))


def users(actor):
    require_admin(actor)
    with transaction(actor) as conn:
        result = conn.execute(
            f"SELECT {PUBLIC_USER} FROM bookstore.app_users ORDER BY user_id"
        ).fetchall()
        log_action(conn, "READ", "app_users", actor=actor)
        return result


def update_user(user_id, role, active, actor):
    require_admin(actor)
    if role not in ("admin", "manager", "reader"):
        raise ValidationError("Невідома роль.")
    if int(user_id) == actor["user_id"] and (role != "admin" or not active):
        raise ValidationError("Не можна позбавити себе прав адміністратора.")
    with transaction(actor) as conn:
        row = conn.execute(
            """
            UPDATE bookstore.app_users
            SET role = %s, is_active = %s
            WHERE user_id = %s
            RETURNING user_id
            """,
            (role, bool(active), user_id),
        ).fetchone()
        if not row:
            raise LookupError("Користувача не знайдено.")


def create_backup(actor):
    require_admin(actor)
    options = db_options()
    pg_bin = os.getenv("PG_BIN")
    candidate = Path(pg_bin) / ("pg_dump.exe" if os.name == "nt" else "pg_dump") if pg_bin else None
    executable = str(candidate) if candidate and candidate.is_file() else shutil.which("pg_dump")
    if not executable:
        raise ValidationError("Не знайдено pg_dump. Необхідно налаштувати PG_BIN у .env.")
    folder = ROOT / "backups"
    folder.mkdir(exist_ok=True)
    name = (
        "bookstore-"
        + datetime.now().strftime("%Y%m%d-%H%M%S")
        + "-"
        + secrets.token_hex(3)
        + ".dump"
    )
    destination = folder / name
    partial = folder / (name + ".partial")
    # Пароль передається через середовище, щоб не потрапити до аргументів процесу.
    environment = dict(os.environ, PGPASSWORD=options["password"])
    result = subprocess.run(
        [
            executable,
            "-h",
            options["host"],
            "-p",
            str(options["port"]),
            "-U",
            options["user"],
            "-d",
            options["dbname"],
            "-w",
            "-Fc",
            "-f",
            str(partial),
        ],
        env=environment,
        capture_output=True,
        timeout=90,
    )
    if result.returncode:
        partial.unlink(missing_ok=True)
        raise ValidationError(
            "Не вдалося створити резервну копію. Необхідно перевірити підключення та версію PostgreSQL."
        )
    # Остаточне ім’я отримує лише успішно створений архів.
    partial.replace(destination)
    with transaction(actor) as conn:
        log_action(
            conn, "BACKUP", "database", {"file": name, "bytes": destination.stat().st_size}, actor
        )
    return destination


def health():
    with transaction() as conn:
        return conn.execute("""
        SELECT current_database() AS database,
               (SELECT count(*) FROM bookstore.books) AS books,
               (SELECT count(*) FROM bookstore.app_users) AS users
        """).fetchone()
