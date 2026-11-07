# URL shortener

FastAPI + async SQLAlchemy + PostgreSQL + Alembic, OAuth2 (password flow, JWT), argon2id.

```bash
docker compose up -d
docker compose exec db psql -U app -d shortener -c "create database shortener_test"
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
uv run pytest
```

Swagger: http://localhost:8000/docs

| Метод | Путь | Что делает |
|---|---|---|
| POST | /auth/register | регистрация |
| POST | /auth/token | логин, выдаёт JWT |
| POST | /links | создать ссылку (или вернуть существующую) |
| GET | /links | свои ссылки |
| DELETE | /links/{id} | soft delete своей ссылки |
| GET | /{code} | 302 / 404 / 419 |
