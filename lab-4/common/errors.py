"""Повідомлення для клієнтів без виведення SQL та параметрів підключення."""

import psycopg


def error_text(exc):
    if isinstance(exc, psycopg.errors.UniqueViolation):
        return "Такий ISBN, логін, email або назва вже існує."
    if isinstance(exc, psycopg.errors.ForeignKeyViolation):
        return "Запис має залежності або вказаний пов’язаний запис не існує."
    if isinstance(exc, psycopg.errors.CheckViolation):
        return "Значення порушує обмеження бази даних."
    if isinstance(exc, psycopg.errors.RaiseException):
        return exc.diag.message_primary
    if isinstance(exc, psycopg.OperationalError):
        return "База даних недоступна. Необхідно перевірити параметри підключення у .env."
    if isinstance(exc, psycopg.Error):
        return "Операцію відхилено базою даних. Зміни скасовані."
    return str(exc) or "Некоректні вхідні дані."
