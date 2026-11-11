# Книгарня

FastAPI-застосунок і консольний клієнт для обліку книг, покупців та замовлень.
База даних - PostgreSQL. Підтримуються ролі, аудит, Excel-звіти, статистика,
API та резервне копіювання.

## Запуск

Параметри підключення задаються в `.env` за шаблоном `.env.example`.

```powershell
cd lab-4
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe run.py
```

Вебінтерфейс: http://127.0.0.1:8000. API-документація: http://127.0.0.1:8000/docs.

Консольний клієнт:

```powershell
.\.venv\Scripts\python.exe -m console_app.main
```

## Початкова база

Лише для нової порожньої PostgreSQL-бази:

```powershell
.\.venv\Scripts\python.exe tools/init_database.py
.\.venv\Scripts\python.exe tools/create_admin.py
```

Навчальний набір завантажується окремо через `tools/init_database.py --demo`
замість звичайного розгортання. Демонстраційні логіни: `admin`,
`manager01`, `manager02`, `reader01`-`reader07`; пароль - `Bookstore2026!`.
Наявну схему скрипт не перезаписує.

## Доступ

`reader` - перегляд; `manager` - створення, редагування, замовлення та експорт;
`admin` - також видалення, користувачі, журнал і резервні копії.
Реєстрація створює роль `reader`. API використовує Bearer-токен,
отриманий через `POST /api/token`.

Для резервного копіювання потрібен `pg_dump` у PATH або параметр `PG_BIN`.
Файли зберігаються в `backups/`.

## Тести

Потрібна окрема PostgreSQL-база із суфіксом `_tests`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
$env:DB_NAME = 'bookstore_lab4_tests'
.\.venv\Scripts\python.exe tools/init_database.py --demo
.\.venv\Scripts\python.exe -m unittest tests.test_integration -v
Remove-Item Env:DB_NAME
```

SQL розміщено в `database/`, ER-модель та опис 3НФ - у `docs/`.
