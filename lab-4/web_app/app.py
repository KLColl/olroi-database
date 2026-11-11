"""FastAPI: HTML-інтерфейс, захищений API та експорт звітів."""

from decimal import Decimal
import hmac
import os
import secrets
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
import psycopg
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

from common import services
from common.catalog import ENTITIES, AccessError, ValidationError, require_editor
from common.config import ROOT, session_secret
from common.database import log_action, transaction
from common.errors import error_text
from web_app.reports import workbook_bytes

app = FastAPI(
    title="Книгарня · API",
    version="1.0.0",
    description="Каталог, замовлення та статистика. Авторизація через POST /api/token.",
)
app.add_middleware(
    SessionMiddleware,
    secret_key=session_secret(),
    session_cookie="bookstore_session",
    max_age=8 * 3600,
    same_site="lax",
    https_only=os.getenv("COOKIE_SECURE", "").lower() == "true",
)
app.mount("/static", StaticFiles(directory=ROOT / "web_app" / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "web_app" / "templates")
templates.env.filters["money"] = lambda value: f"{value or 0:,.2f}".replace(",", " ")
templates.env.filters["stamp"] = lambda value: value.strftime("%d.%m.%Y %H:%M") if value else "-"
templates.env.filters["status_ua"] = lambda value: {
    "Draft": "Чернетка",
    "Confirmed": "Підтверджено",
    "Cancelled": "Скасовано",
}.get(value, value)
bearer = HTTPBearer(auto_error=False)


class LoginRequired(Exception):
    pass


def actor(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
):
    # Явно передана авторизація має пріоритет: помилковий токен не підміняється чинною сесією.
    if request.headers.get("authorization"):
        user = services.get_user(token=credentials.credentials) if credentials else None
    else:
        user = services.get_user(user_id=request.session.get("user_id"))
    if not user:
        if request.url.path.startswith("/api/"):
            raise HTTPException(
                401, "Потрібна авторизація.", headers={"WWW-Authenticate": "Bearer"}
            )
        raise LoginRequired()
    return user


Actor = Annotated[dict, Depends(actor)]


def render(request, name, user=None, **context):
    csrf = request.session.setdefault("csrf", secrets.token_urlsafe(32))
    return templates.TemplateResponse(
        request=request,
        name=name,
        context=dict(
            user=user,
            csrf=csrf,
            entities=ENTITIES,
            current_path=request.url.path,
            notice=request.query_params.get("notice", ""),
            **context,
        ),
    )


def check_csrf(request, token):
    expected = request.session.get("csrf", "")
    if not expected or not isinstance(token, str) or not hmac.compare_digest(token, expected):
        raise AccessError("Форма застаріла. Оновіть сторінку та повторіть дію.")


async def form_values(request):
    values = dict(await request.form())
    check_csrf(request, values.pop("csrf", None))
    return values


def api_csrf(request):
    # Сесія надсилається браузером автоматично, тому потребує CSRF-токена; Bearer передається явно.
    if not request.headers.get("authorization"):
        check_csrf(request, request.headers.get("x-csrf-token"))


def filters(request):
    query = request.query_params
    try:
        page = max(1, int(query.get("page", "1")))
    except ValueError:
        raise ValidationError("Некоректний номер сторінки.")
    return dict(
        q=query.get("q", ""),
        sort=query.get("sort", ""),
        direction=query.get("direction", "asc"),
        page=page,
        category=query.get("category", ""),
        min_price=query.get("min_price", ""),
        max_price=query.get("max_price", ""),
    )


@app.exception_handler(LoginRequired)
async def login_required(request, exc):
    return RedirectResponse("/login", status_code=303)


async def application_error(request, exc):
    if isinstance(exc, AccessError):
        status = 403
    elif isinstance(exc, LookupError):
        status = 404
    elif isinstance(exc, psycopg.OperationalError):
        status = 503
    elif isinstance(exc, (psycopg.errors.UniqueViolation, psycopg.errors.ForeignKeyViolation)):
        status = 409
    else:
        status = 422
    message = error_text(exc)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": message}, status_code=status)
    response = render(request, "error.html", title="Не вдалося виконати дію", message=message)
    response.status_code = status
    return response


for error_type in (ValidationError, AccessError, LookupError, ValueError, psycopg.Error):
    app.add_exception_handler(error_type, application_error)


@app.get("/login", response_class=HTMLResponse, include_in_schema=False)
def login_form(request: Request):
    return render(request, "auth.html", mode="login", title="З поверненням")


@app.get("/register", response_class=HTMLResponse, include_in_schema=False)
def registration_form(request: Request):
    return render(request, "auth.html", mode="register", title="Створити обліковий запис")


@app.post("/login", include_in_schema=False)
async def login(request: Request):
    data = await form_values(request)
    user = await run_in_threadpool(
        services.authenticate, data.get("username", ""), data.get("password", "")
    )
    if not user:
        response = render(
            request,
            "auth.html",
            mode="login",
            title="З поверненням",
            error="Неправильний логін або пароль.",
        )
        response.status_code = 401
        return response
    request.session.clear()
    request.session.update(user_id=user["user_id"], csrf=secrets.token_urlsafe(32))
    return RedirectResponse("/", status_code=303)


@app.post("/register", include_in_schema=False)
async def registration(request: Request):
    data = await form_values(request)
    await run_in_threadpool(
        services.register, data.get("username", ""), data.get("email", ""), data.get("password", "")
    )
    return RedirectResponse(
        "/login?notice=Обліковий+запис+створено.+Авторизація+доступна.", status_code=303
    )


@app.post("/logout", include_in_schema=False)
async def logout(request: Request, user: Actor):
    await form_values(request)

    def record():
        with transaction(user) as conn:
            log_action(conn, "LOGOUT", "app_users", actor=user)

    await run_in_threadpool(record)
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(request: Request, user: Actor):
    stats = services.statistics(user)
    return render(
        request,
        "dashboard.html",
        user,
        title="Огляд книгарні",
        stats=stats,
        chart_data=jsonable_encoder({"categories": stats["categories"], "daily": stats["daily"]}),
    )


@app.get("/catalog/{entity}", response_class=HTMLResponse, include_in_schema=False)
def catalog(request: Request, entity: str, user: Actor):
    data = services.list_entities(entity, user, **filters(request))
    return render(
        request,
        "catalog.html",
        user,
        title=ENTITIES[entity]["label"],
        entity=entity,
        conf=ENTITIES[entity],
        data=data,
        refs=services.references(user),
        query=dict(request.query_params),
    )


@app.get("/catalog/{entity}/new", response_class=HTMLResponse, include_in_schema=False)
def new_form(request: Request, entity: str, user: Actor):
    require_editor(user)
    if entity not in ENTITIES:
        raise LookupError("Невідома сутність.")
    return render(
        request,
        "form.html",
        user,
        title="Додати запис",
        entity=entity,
        conf=ENTITIES[entity],
        values={},
        refs=services.references(user),
        item_id=None,
    )


@app.get("/catalog/{entity}/{item_id}/edit", response_class=HTMLResponse, include_in_schema=False)
def edit_form(request: Request, entity: str, item_id: int, user: Actor):
    require_editor(user)
    values = services.get_entity(entity, item_id, user)
    return render(
        request,
        "form.html",
        user,
        title="Редагувати запис",
        entity=entity,
        conf=ENTITIES[entity],
        values=values,
        refs=services.references(user),
        item_id=item_id,
    )


@app.post("/catalog/{entity}/save", include_in_schema=False)
async def save_form(request: Request, entity: str, user: Actor):
    data = await form_values(request)
    item_id = int(data.pop("item_id")) if data.get("item_id") else None
    await run_in_threadpool(services.save_entity, entity, data, user, item_id)
    return RedirectResponse(f"/catalog/{entity}?notice=Зміни+збережено", status_code=303)


@app.post("/catalog/{entity}/{item_id}/delete", include_in_schema=False)
async def delete_form(request: Request, entity: str, item_id: int, user: Actor):
    await form_values(request)
    await run_in_threadpool(services.delete_entity, entity, item_id, user)
    return RedirectResponse(f"/catalog/{entity}?notice=Запис+видалено", status_code=303)


@app.get("/orders", response_class=HTMLResponse, include_in_schema=False)
def order_list(request: Request, user: Actor):
    status = request.query_params.get("status", "")
    return render(
        request,
        "orders.html",
        user,
        title="Замовлення",
        rows=services.orders(user, status),
        refs=services.references(user),
        selected_status=status,
    )


@app.post("/orders/new", include_in_schema=False)
async def new_order(request: Request, user: Actor):
    data = await form_values(request)
    order_id = await run_in_threadpool(services.create_order, data.get("customer_id"), user)
    return RedirectResponse(f"/orders/{order_id}", status_code=303)


@app.get("/orders/{order_id}", response_class=HTMLResponse, include_in_schema=False)
def order_page(request: Request, order_id: int, user: Actor):
    order, items = services.order_detail(order_id, user)
    return render(
        request,
        "order.html",
        user,
        title=f"Замовлення №{order_id}",
        order=order,
        items=items,
        books=services.list_entities("books", user, limit=1000)["rows"],
        refs=services.references(user),
    )


@app.post("/orders/{order_id}/{action}", include_in_schema=False)
async def perform_order_action(request: Request, order_id: int, action: str, user: Actor):
    data = await form_values(request)
    await run_in_threadpool(
        services.order_action,
        order_id,
        action,
        user,
        data.get("book_id"),
        data.get("quantity"),
        data.get("customer_id"),
    )
    return RedirectResponse(
        "/orders" if action == "delete" else f"/orders/{order_id}", status_code=303
    )


@app.get("/audit", response_class=HTMLResponse, include_in_schema=False)
def audit_page(request: Request, user: Actor):
    return render(
        request,
        "audit.html",
        user,
        title="Журнал операцій",
        data=services.audit_log(
            user,
            request.query_params.get("action", ""),
            request.query_params.get("q", ""),
            filters(request)["page"],
        ),
    )


@app.get("/users", response_class=HTMLResponse, include_in_schema=False)
def user_page(request: Request, user: Actor):
    return render(request, "users.html", user, title="Користувачі", rows=services.users(user))


@app.post("/users/{user_id}", include_in_schema=False)
async def user_save(request: Request, user_id: int, user: Actor):
    data = await form_values(request)
    await run_in_threadpool(
        services.update_user, user_id, data.get("role"), data.get("is_active") == "on", user
    )
    return RedirectResponse("/users?notice=Права+оновлено", status_code=303)


@app.get("/tools", response_class=HTMLResponse, include_in_schema=False)
def tools_page(request: Request, user: Actor):
    return render(request, "tools.html", user, title="Звіти та інтеграція")


@app.post("/tools/token", include_in_schema=False)
async def token_form(request: Request, user: Actor):
    await form_values(request)
    token = await run_in_threadpool(services.issue_api_token, user)
    return render(request, "tools.html", user, title="Звіти та інтеграція", token=token)


@app.post("/tools/backup", include_in_schema=False)
async def backup_form(request: Request, user: Actor):
    await form_values(request)
    path = await run_in_threadpool(services.create_backup, user)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@app.get("/reports/{report}.xlsx", include_in_schema=False)
def report_download(
    request: Request, report: Literal["books", "orders", "statistics"], user: Actor
):
    require_editor(user)
    if report == "books":
        search = filters(request)
        search.pop("page")
        rows, page = [], 1
        while True:
            batch = services.list_entities("books", user, **search, page=page, limit=1000)
            rows.extend(batch["rows"])
            if page >= batch["pages"]:
                break
            page += 1
        columns = [
            ("isbn", "ISBN"),
            ("title", "Назва"),
            ("author_name", "Автор"),
            ("category_name", "Категорія"),
            ("price", "Ціна, грн"),
            ("stock_quantity", "На складі"),
        ]
    elif report == "orders":
        rows = services.orders(user)
        columns = [
            ("order_id", "Замовлення"),
            ("customer_name", "Покупець"),
            ("status", "Статус"),
            ("created_at", "Створено"),
            ("order_total", "Сума, грн"),
        ]
    else:
        rows = services.statistics(user)["categories"]
        columns = [("category_name", "Категорія"), ("revenue", "Продажі, грн")]
    payload = workbook_bytes(report, columns, rows)
    with transaction(user) as conn:
        log_action(conn, "EXPORT", report, {"rows": len(rows), "format": "xlsx"}, user)
    return Response(
        payload,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="bookstore-{report}.xlsx"'},
    )


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=1, max_length=128)


class BookPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    isbn: str = Field(pattern=r"^\d{13}$")
    title: str = Field(min_length=1, max_length=500)
    author_id: int = Field(gt=0)
    category_id: int = Field(gt=0)
    publication_year: int = Field(ge=1450, le=2100)
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    stock_quantity: int = Field(ge=0, le=1_000_000)


class OrderPayload(BaseModel):
    customer_id: int = Field(gt=0)


class ItemPayload(BaseModel):
    book_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


@app.post("/api/token", tags=["Authentication"])
def api_token(data: Credentials):
    user = services.authenticate(data.username, data.password)
    if not user:
        raise HTTPException(401, "Неправильний логін або пароль.")
    return {
        "access_token": services.issue_api_token(user),
        "token_type": "bearer",
        "role": user["role"],
    }


@app.get("/api/books", tags=["Books"])
def api_books(
    user: Actor,
    q: str = Query("", max_length=200),
    page: int = Query(1, ge=1),
    category: int | None = Query(None, gt=0),
    min_price: Decimal | None = Query(None, ge=0),
    max_price: Decimal | None = Query(None, ge=0),
    sort: Literal[
        "book_id", "title", "price", "stock_quantity", "author_name", "category_name"
    ] = "book_id",
    direction: Literal["asc", "desc"] = "asc",
):
    return services.list_entities(
        "books",
        user,
        q=q,
        page=page,
        category=category,
        min_price=min_price,
        max_price=max_price,
        sort=sort,
        direction=direction,
    )


@app.get("/api/books/{book_id}", tags=["Books"])
def api_book(book_id: int, user: Actor):
    return services.get_entity("books", book_id, user)


@app.post("/api/books", status_code=201, tags=["Books"])
def api_create_book(request: Request, data: BookPayload, user: Actor):
    api_csrf(request)
    return {"book_id": services.save_entity("books", data.model_dump(), user)}


@app.put("/api/books/{book_id}", tags=["Books"])
def api_update_book(request: Request, book_id: int, data: BookPayload, user: Actor):
    api_csrf(request)
    return {"book_id": services.save_entity("books", data.model_dump(), user, book_id)}


@app.delete("/api/books/{book_id}", status_code=204, tags=["Books"])
def api_delete_book(request: Request, book_id: int, user: Actor):
    api_csrf(request)
    services.delete_entity("books", book_id, user)
    return Response(status_code=204)


@app.get("/api/statistics", tags=["Analytics"])
def api_statistics(user: Actor):
    return services.statistics(user)


@app.get("/api/orders", tags=["Orders"])
def api_orders(user: Actor, status: str = ""):
    return services.orders(user, status)


@app.post("/api/orders", status_code=201, tags=["Orders"])
def api_create_order(request: Request, data: OrderPayload, user: Actor):
    api_csrf(request)
    return {"order_id": services.create_order(data.customer_id, user)}


@app.get("/api/orders/{order_id}", tags=["Orders"])
def api_order(order_id: int, user: Actor):
    order, items = services.order_detail(order_id, user)
    return {"order": order, "items": items}


@app.post("/api/orders/{order_id}/items", tags=["Orders"])
def api_order_item(request: Request, order_id: int, data: ItemPayload, user: Actor):
    api_csrf(request)
    services.order_action(order_id, "item", user, data.book_id, data.quantity)
    return {"success": True}


@app.post("/api/orders/{order_id}/confirm", tags=["Orders"])
def api_confirm(request: Request, order_id: int, user: Actor):
    api_csrf(request)
    services.order_action(order_id, "confirm", user)
    return {"success": True}


@app.post("/api/orders/{order_id}/cancel", tags=["Orders"])
def api_cancel(request: Request, order_id: int, user: Actor):
    api_csrf(request)
    services.order_action(order_id, "cancel", user)
    return {"success": True}
