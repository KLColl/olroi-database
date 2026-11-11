"""Налаштування з локального .env, який не потрапляє до Git."""

import os
from pathlib import Path
import secrets

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def db_options():
    return dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "bookstore_lab4"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        connect_timeout=5,
    )


def session_secret():
    if os.getenv("SESSION_SECRET"):
        return os.environ["SESSION_SECRET"]
    folder = ROOT / ".instance"
    folder.mkdir(exist_ok=True)
    path = folder / "session.key"
    # Режим x створює ключ лише раз; повторні запуски використовують той самий підпис сесій.
    try:
        with path.open("x", encoding="ascii") as stream:
            stream.write(secrets.token_hex(32))
    except FileExistsError:
        pass
    return path.read_text(encoding="ascii").strip()
