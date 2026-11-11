"""Білий список сутностей, полів і правил валідації для CLI, HTML та API."""

from decimal import Decimal, InvalidOperation
import re


class ValidationError(ValueError):
    pass


class AccessError(PermissionError):
    pass


# Поля описано як (назва, підпис, тип, обов’язковість); author/category позначають зовнішні ключі.
ENTITIES = {
    "books": dict(
        label="Книги",
        singular="Книгу",
        key="book_id",
        fields=[
            ("isbn", "ISBN", "isbn", True),
            ("title", "Назва", "text", True),
            ("author_id", "Автор", "author", True),
            ("category_id", "Категорія", "category", True),
            ("publication_year", "Рік видання", "year", True),
            ("price", "Ціна, грн", "money", True),
            ("stock_quantity", "На складі", "stock", True),
        ],
    ),
    "authors": dict(
        label="Автори",
        singular="Автора",
        key="author_id",
        fields=[
            ("first_name", "Ім’я", "text", True),
            ("last_name", "Прізвище", "text", True),
            ("country", "Країна", "text", True),
        ],
    ),
    "categories": dict(
        label="Категорії",
        singular="Категорію",
        key="category_id",
        fields=[("category_name", "Назва", "text", True), ("description", "Опис", "text", False)],
    ),
    "customers": dict(
        label="Покупці",
        singular="Покупця",
        key="customer_id",
        fields=[
            ("full_name", "ПІБ", "text", True),
            ("email", "Email", "email", True),
            ("phone", "Телефон", "phone", False),
        ],
    ),
}


def require_editor(actor):
    if not actor or actor["role"] not in ("admin", "manager"):
        raise AccessError("Ця операція доступна адміністратору та менеджеру.")


def require_admin(actor):
    if not actor or actor["role"] != "admin":
        raise AccessError("Ця операція доступна лише адміністратору.")


def validate_entity(entity, data):
    if entity not in ENTITIES:
        raise ValidationError("Невідома сутність.")
    result = {}
    for name, label, kind, required in ENTITIES[entity]["fields"]:
        raw = str(data.get(name, "") if data.get(name) is not None else "").strip()
        if not raw:
            if required:
                raise ValidationError(f"{label}: обов’язкове поле.")
            result[name] = None
            continue
        if len(raw) > 500:
            raise ValidationError(f"{label}: не більше 500 символів.")
        if kind in ("year", "stock", "author", "category"):
            if not re.fullmatch(r"\d+", raw):
                raise ValidationError(f"{label}: потрібне ціле число.")
            value = int(raw)
            low, high = (
                (1450, 2100)
                if kind == "year"
                else ((0, 1_000_000) if kind == "stock" else (1, 2**63 - 1))
            )
            if not low <= value <= high:
                raise ValidationError(f"{label}: значення поза діапазоном {low}-{high}.")
            result[name] = value
        elif kind == "money":
            try:
                value = Decimal(raw.replace(",", "."))
                if not value.is_finite() or not 0 <= value <= Decimal("99999999.99"):
                    raise InvalidOperation
                if value != value.quantize(Decimal(".01")):
                    raise InvalidOperation
                result[name] = value.quantize(Decimal(".01"))
            except InvalidOperation:
                raise ValidationError(
                    "Ціна: невід’ємне число з максимум двома десятковими знаками."
                )
        elif kind == "email":
            raw = raw.lower()
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", raw):
                raise ValidationError("Некоректна електронна адреса.")
            result[name] = raw
        elif kind == "isbn":
            if not re.fullmatch(r"\d{13}", raw):
                raise ValidationError("ISBN має містити рівно 13 цифр.")
            if sum(int(n) * (1 if i % 2 == 0 else 3) for i, n in enumerate(raw)) % 10:
                raise ValidationError("Неправильна контрольна цифра ISBN-13.")
            result[name] = raw
        elif kind == "phone":
            if not re.fullmatch(r"\+?[0-9 ()-]{7,20}", raw):
                raise ValidationError("Некоректний номер телефону.")
            result[name] = raw
        else:
            result[name] = raw
    return result


def validate_registration(username, email, password):
    username, email = username.strip().lower(), email.strip().lower()
    if not re.fullmatch(r"[a-z0-9_.-]{3,40}", username):
        raise ValidationError("Логін: 3-40 латинських малих літер, цифр або символів _.-")
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValidationError("Некоректна електронна адреса.")
    if (
        not 8 <= len(password) <= 128
        or not any(c.isalpha() for c in password)
        or not any(c.isdigit() for c in password)
    ):
        raise ValidationError("Пароль: 8-128 символів, щонайменше одна літера й одна цифра.")
    return username, email
