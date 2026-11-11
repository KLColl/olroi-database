"""DB_NAME обов'язково має закінчуватися на _tests: робоча БД не змінюється."""

from io import BytesIO
from contextlib import redirect_stdout
from io import StringIO
import os
import re
import secrets
import subprocess
import unittest
from unittest.mock import patch

import psycopg
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from common import services
from common.catalog import AccessError
from common.config import db_options
from common.database import transaction
from common.security import verify_password
from web_app.app import app
from web_app.reports import workbook_bytes


def isbn(prefix):
    return prefix + str(
        (-sum(int(n) * (1 if i % 2 == 0 else 3) for i, n in enumerate(prefix))) % 10
    )


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not db_options()["dbname"].endswith("_tests"):
            raise RuntimeError("Інтеграційні тести дозволені лише в окремій БД із суфіксом _tests.")
        cls.client = TestClient(app, raise_server_exceptions=False)
        cls.tokens = {}
        for name in ("admin", "manager01", "reader01"):
            response = cls.client.post(
                "/api/token", json={"username": name, "password": "Bookstore2026!"}
            )
            if response.status_code != 200:
                raise RuntimeError(response.text)
            cls.tokens[name] = {"Authorization": "Bearer " + response.json()["access_token"]}

    def test_01_schema_and_seed(self):
        with transaction() as conn:
            for table in (
                "authors",
                "categories",
                "books",
                "customers",
                "orders",
                "order_items",
                "app_users",
                "activity_log",
            ):
                self.assertGreaterEqual(
                    conn.execute(f"SELECT count(*) AS n FROM bookstore.{table}").fetchone()["n"], 10
                )
            self.assertEqual(
                conn.execute(
                    "SELECT count(*) AS n FROM information_schema.routines WHERE routine_schema='bookstore' AND routine_type='PROCEDURE'"
                ).fetchone()["n"],
                3,
            )
            self.assertGreaterEqual(
                conn.execute(
                    "SELECT count(DISTINCT trigger_name) AS n FROM information_schema.triggers WHERE trigger_schema='bookstore'"
                ).fetchone()["n"],
                8,
            )

    def test_02_authentication_and_role_enforcement(self):
        self.assertEqual(self.client.get("/api/books").status_code, 401)
        self.assertEqual(
            self.client.get("/api/books", headers={"Authorization": "Bearer invalid"}).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                "/api/token", json={"username": "admin", "password": "wrong"}
            ).status_code,
            401,
        )
        body = dict(
            isbn=isbn("978123456780"),
            title="Forbidden",
            author_id=1,
            category_id=1,
            publication_year=2026,
            price="20.00",
            stock_quantity=5,
        )
        self.assertEqual(
            self.client.post("/api/books", headers=self.tokens["reader01"], json=body).status_code,
            403,
        )
        self.assertEqual(
            self.client.delete("/api/books/1", headers=self.tokens["manager01"]).status_code, 403
        )
        manager = services.get_user(token=self.tokens["manager01"]["Authorization"].split()[1])
        with self.assertRaises(AccessError):
            services.users(manager)

    def test_03_crud_search_validation_and_escaping(self):
        body = dict(
            isbn=isbn("978123456789"),
            title="<script>alert(1)</script> TEST CRUD",
            author_id=1,
            category_id=1,
            publication_year=2026,
            price="123.45",
            stock_quantity=6,
        )
        admin = self.tokens["admin"]
        created = self.client.post("/api/books", json=body, headers=admin)
        self.assertEqual(created.status_code, 201, created.text)
        book_id = created.json()["book_id"]
        try:
            self.assertEqual(
                self.client.get(f"/api/books/{book_id}", headers=admin).json()["title"],
                body["title"],
            )
            self.assertEqual(
                self.client.post("/api/books", json=body, headers=admin).status_code, 409
            )
            self.assertEqual(
                self.client.post(
                    "/api/books", json={**body, "price": "-1"}, headers=admin
                ).status_code,
                422,
            )
            self.assertEqual(
                self.client.post(
                    "/api/books", json={**body, "isbn": "123"}, headers=admin
                ).status_code,
                422,
            )
            updated = self.client.put(
                f"/api/books/{book_id}", json={**body, "price": "150.00"}, headers=admin
            )
            self.assertEqual(updated.status_code, 200, updated.text)
            search = self.client.get(
                "/api/books",
                params={"q": "TEST CRUD", "direction": "desc", "sort": "price"},
                headers=admin,
            )
            self.assertEqual(search.json()["total"], 1)
            injected = self.client.get("/api/books", params={"q": "' OR 1=1 --"}, headers=admin)
            self.assertEqual(injected.json()["total"], 0)
            self.assertGreaterEqual(
                self.client.get("/api/books", headers=admin).json()["total"], 21
            )
            # HTML має екранувати вставлений користувачем script, а не виконувати його.
            html = self.client.get("/catalog/books", params={"q": "TEST CRUD"}, headers=admin)
            self.assertEqual(html.status_code, 200, html.text[:400])
            self.assertIn("&lt;script&gt;", html.text)
            self.assertNotIn("<script>alert(1)</script>", html.text)
        finally:
            response = self.client.delete(f"/api/books/{book_id}", headers=admin)
            self.assertEqual(response.status_code, 204, response.text)
        self.assertEqual(self.client.get(f"/api/books/{book_id}", headers=admin).status_code, 404)

    def test_04_order_transaction_and_rollback(self):
        admin = self.tokens["admin"]
        before = self.client.get("/api/books/1", headers=admin).json()["stock_quantity"]
        order_id = self.client.post("/api/orders", json={"customer_id": 1}, headers=admin).json()[
            "order_id"
        ]
        self.assertEqual(
            self.client.post(f"/api/orders/{order_id}/confirm", headers=admin).status_code, 422
        )
        self.assertEqual(
            self.client.post(
                f"/api/orders/{order_id}/items",
                json={"book_id": 1, "quantity": 1000000},
                headers=admin,
            ).status_code,
            200,
        )
        failed = self.client.post(f"/api/orders/{order_id}/confirm", headers=admin)
        self.assertEqual(failed.status_code, 422, failed.text)
        self.assertEqual(
            self.client.get("/api/books/1", headers=admin).json()["stock_quantity"], before
        )
        self.assertEqual(
            self.client.get(f"/api/orders/{order_id}", headers=admin).json()["order"]["status"],
            "Draft",
        )
        self.client.post(
            f"/api/orders/{order_id}/items", json={"book_id": 1, "quantity": 2}, headers=admin
        )
        self.assertEqual(
            self.client.post(f"/api/orders/{order_id}/confirm", headers=admin).status_code, 200
        )
        self.assertEqual(
            self.client.get("/api/books/1", headers=admin).json()["stock_quantity"], before - 2
        )
        self.assertEqual(
            self.client.post(
                f"/api/orders/{order_id}/items", json={"book_id": 1, "quantity": 3}, headers=admin
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(f"/api/orders/{order_id}/confirm", headers=admin).status_code, 422
        )
        self.assertEqual(
            self.client.post(f"/api/orders/{order_id}/cancel", headers=admin).status_code, 200
        )
        self.assertEqual(
            self.client.post(f"/api/orders/{order_id}/cancel", headers=admin).status_code, 422
        )
        self.assertEqual(
            self.client.get("/api/books/1", headers=admin).json()["stock_quantity"], before
        )

    def test_05_all_pages_excel_and_audit(self):
        for path in (
            "/",
            "/catalog/books",
            "/catalog/authors",
            "/catalog/categories",
            "/catalog/customers",
            "/catalog/books/new",
            "/catalog/books/1/edit",
            "/orders",
            "/orders/1",
            "/audit",
            "/users",
            "/tools",
            "/docs",
        ):
            response = self.client.get(path, headers=self.tokens["admin"])
            self.assertEqual(response.status_code, 200, path + ": " + response.text[:300])
        for kind in ("books", "orders", "statistics"):
            response = self.client.get(f"/reports/{kind}.xlsx", headers=self.tokens["admin"])
            self.assertEqual(
                response.status_code,
                200,
                response.text[:300] if response.status_code != 200 else "",
            )
            wb = load_workbook(BytesIO(response.content))
            self.assertGreater(wb.active.max_row, 1)
            self.assertEqual(wb.active.freeze_panes, "A2")
        with transaction() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT count(*) AS n FROM bookstore.activity_log WHERE new_data ? 'password_hash' OR new_data ? 'api_token_hash' OR old_data ? 'password_hash' OR old_data ? 'api_token_hash'"
                ).fetchone()["n"],
                0,
            )
            actions = {
                r["action"]
                for r in conn.execute(
                    "SELECT DISTINCT action FROM bookstore.activity_log"
                ).fetchall()
            }
            self.assertTrue({"INSERT", "UPDATE", "DELETE", "READ", "LOGIN", "EXPORT"} <= actions)
            self.assertTrue(
                conn.execute(
                    "SELECT EXISTS(SELECT 1 FROM bookstore.activity_log WHERE username='admin' AND action='UPDATE') AS ok"
                ).fetchone()["ok"]
            )

    def test_06_browser_session_csrf_registration(self):
        client = TestClient(app, raise_server_exceptions=False)
        self.assertEqual(client.get("/", follow_redirects=False).status_code, 303)
        self.assertEqual(
            client.post(
                "/login", data={"username": "admin", "password": "Bookstore2026!"}
            ).status_code,
            403,
        )
        page = client.get("/login")
        csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
        login = client.post(
            "/login",
            data={"username": "admin", "password": "Bookstore2026!", "csrf": csrf},
            follow_redirects=False,
        )
        self.assertEqual(login.status_code, 303, login.text)
        page = client.get("/")
        self.assertEqual(page.status_code, 200, page.text[:300])
        self.assertEqual(client.post("/api/orders", json={"customer_id": 1}).status_code, 403)
        csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
        self.assertEqual(
            client.post("/logout", data={"csrf": csrf}, follow_redirects=False).status_code, 303
        )
        page = client.get("/register")
        csrf = re.search(r'name="csrf" value="([^"]+)"', page.text).group(1)
        name = "test" + secrets.token_hex(4)
        registered = client.post(
            "/register",
            data={
                "username": name,
                "email": name + "@example.com",
                "password": "Register2026!",
                "role": "admin",
                "csrf": csrf,
            },
            follow_redirects=False,
        )
        self.assertEqual(registered.status_code, 303, registered.text)
        with transaction() as conn:
            user = conn.execute(
                "SELECT role,password_hash FROM bookstore.app_users WHERE username=%s", (name,)
            ).fetchone()
            self.assertEqual(user["role"], "reader")
            self.assertTrue(verify_password("Register2026!", user["password_hash"]))

    def test_07_backup_is_valid_archive(self):
        response = self.client.post(
            "/tools/backup", headers=self.tokens["admin"], data={"csrf": "invalid"}
        )
        self.assertEqual(response.status_code, 403)
        admin = services.get_user(token=self.tokens["admin"]["Authorization"].split()[1])
        path = services.create_backup(admin)
        executable = os.path.join(
            os.getenv("PG_BIN", r"C:\Program Files\PostgreSQL\18\bin"), "pg_restore.exe"
        )
        result = subprocess.run([executable, "--list", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bookstore", result.stdout)
        self.assertGreater(path.stat().st_size, 5000)
        # Перевіряємо не лише заголовок архіву, а й відновлення у НОВУ тестову БД.
        target = "bookstore_restore_" + secrets.token_hex(4) + "_tests"
        options = db_options()
        environment = dict(os.environ, PGPASSWORD=options["password"])
        with psycopg.connect(**options, autocommit=True) as conn:
            conn.execute(
                psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(target))
            )
        try:
            restored = subprocess.run(
                [
                    executable,
                    "-h",
                    options["host"],
                    "-p",
                    str(options["port"]),
                    "-U",
                    options["user"],
                    "-d",
                    target,
                    "-w",
                    "--exit-on-error",
                    "--single-transaction",
                    str(path),
                ],
                env=environment,
                capture_output=True,
                text=True,
            )
            self.assertEqual(restored.returncode, 0, restored.stderr)
            with psycopg.connect(**{**options, "dbname": target}) as conn:
                self.assertEqual(
                    conn.execute("SELECT count(*) FROM bookstore.books").fetchone()[0], 20
                )
                self.assertGreaterEqual(
                    conn.execute("SELECT count(*) FROM bookstore.activity_log").fetchone()[0], 10
                )
        finally:
            with psycopg.connect(**options, autocommit=True) as conn:
                conn.execute(
                    psycopg.sql.SQL("DROP DATABASE {}").format(psycopg.sql.Identifier(target))
                )

    def test_08_export_text_cannot_become_excel_formula(self):
        payload = workbook_bytes("Test", [("title", "Назва")], [{"title": '=HYPERLINK("bad")'}])
        book = load_workbook(BytesIO(payload), data_only=False)
        self.assertEqual(book.active["A2"].data_type, "s")
        self.assertTrue(book.active["A2"].value.startswith("'="))

    def test_09_console_interactive_crud(self):
        from console_app.main import main

        number = isbn("978123456788")

        def find_id():
            with transaction() as conn:
                return str(
                    conn.execute(
                        "SELECT book_id FROM bookstore.books WHERE isbn=%s", (number,)
                    ).fetchone()["book_id"]
                )

        values = iter(
            [
                "admin",
                "2",
                number,
                "CONSOLE CRUD",
                "1",
                "1",
                "2026",
                "100.00",
                "4",
                "3",
                find_id,
                "",
                "",
                "",
                "",
                "",
                "200.00",
                "",
                "1",
                "CONSOLE CRUD",
                "4",
                find_id,
                "DELETE",
                "1",
                "CONSOLE CRUD",
                "0",
            ]
        )

        def answer(prompt=""):
            value = next(values)
            return value() if callable(value) else value

        output = StringIO()
        with patch("sys.argv", ["console"]), patch("builtins.input", answer), patch(
            "console_app.main.getpass", return_value="Bookstore2026!"
        ), redirect_stdout(output):
            main()
        self.assertEqual(output.getvalue().count("Збережено, ID:"), 2)
        self.assertIn("Запис видалено.", output.getvalue())
        self.assertIn("200.00", output.getvalue())
        with transaction() as conn:
            self.assertEqual(
                conn.execute(
                    "SELECT count(*) AS n FROM bookstore.books WHERE isbn=%s", (number,)
                ).fetchone()["n"],
                0,
            )

    def test_10_reference_crud(self):
        admin = services.get_user(token=self.tokens["admin"]["Authorization"].split()[1])
        cases = [
            (
                "authors",
                dict(first_name="Тест", last_name="CRUD", country="Україна"),
                "country",
                "Польща",
            ),
            (
                "categories",
                dict(category_name="TEST CRUD CATEGORY", description="Опис"),
                "description",
                "Новий опис",
            ),
            (
                "customers",
                dict(full_name="Тест CRUD", email="test-crud@example.com", phone="+380501234567"),
                "full_name",
                "Оновлений CRUD",
            ),
        ]
        for entity, fields, key, updated in cases:
            item_id = services.save_entity(entity, fields, admin)
            services.save_entity(entity, {**fields, key: updated}, admin, item_id)
            self.assertEqual(services.get_entity(entity, item_id, admin)[key], updated)
            services.delete_entity(entity, item_id, admin)
            with self.assertRaises(LookupError):
                services.get_entity(entity, item_id, admin)

    def test_11_standard_setup_does_not_create_demo_accounts(self):
        from tools.init_database import initialize
        from tools.create_admin import main as create_admin
        from common.catalog import ValidationError

        target = "bookstore_empty_" + secrets.token_hex(4) + "_tests"
        options = db_options()
        with psycopg.connect(**options, autocommit=True) as conn:
            conn.execute(
                psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(target))
            )
        try:
            with patch.dict(os.environ, {"DB_NAME": target}), redirect_stdout(StringIO()):
                initialize()
                with transaction() as conn:
                    self.assertEqual(
                        conn.execute("SELECT count(*) AS n FROM bookstore.app_users").fetchone()[
                            "n"
                        ],
                        0,
                    )
                    self.assertEqual(
                        conn.execute("SELECT count(*) AS n FROM bookstore.books").fetchone()["n"], 0
                    )
                with patch(
                    "builtins.input", side_effect=["initialadmin", "initial@example.com"]
                ), patch("tools.create_admin.getpass", return_value="Unique2026!"):
                    create_admin()
                with transaction() as conn:
                    row = conn.execute(
                        "SELECT role,password_hash FROM bookstore.app_users"
                    ).fetchone()
                    self.assertEqual(row["role"], "admin")
                    self.assertTrue(verify_password("Unique2026!", row["password_hash"]))
                with patch(
                    "builtins.input", side_effect=["secondadmin", "second@example.com"]
                ), patch("tools.create_admin.getpass", return_value="Unique2026!"):
                    with self.assertRaises(ValidationError):
                        create_admin()
        finally:
            with psycopg.connect(**options, autocommit=True) as conn:
                conn.execute(
                    psycopg.sql.SQL("DROP DATABASE {}").format(psycopg.sql.Identifier(target))
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
