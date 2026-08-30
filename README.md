# BuyMeLaterBot

Telegram-бот для семейных списков покупок и дел с REST API для Home Assistant.

## Стек

- Python 3.12, aiogram 3, FastAPI, SQLAlchemy 2 async
- PostgreSQL (`pg.sweethome.local`, БД `buymelater`)
- Yargy + dateparser для русскоязычных напоминаний
- APScheduler для уведомлений

## Инфраструктура

| Сервис | Адрес |
|--------|-------|
| Bot LXC | `172.16.10.160:8080` |
| PostgreSQL | `pg.sweethome.local` (`172.16.10.150:5432`) |
| Home Assistant | `https://makeinstall.duckdns.org` |

## Быстрый старт (dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

cp deploy/.env.example .env
# заполнить TELEGRAM_BOT_TOKEN, API_TOKEN, DATABASE_URL

alembic upgrade head
python main.py
```

## Docker (LXC 172.16.10.160)

```bash
cd deploy
cp .env.example .env
docker compose up -d --build
docker compose exec app alembic upgrade head
```

## API

- `GET /health` — без авторизации
- `GET /api/v1/scopes` — `Authorization: Bearer $API_TOKEN`
- CRUD: `/api/v1/lists/{id}/items`, `/api/v1/items/{id}`

## Telegram

Примеры фраз:

- `напомни купить хлеб в 17:00`
- `напомни записаться к стоматологу 01.09.2026 в 09:00`

Команды: `/start`, `/shopping`, `/tasks`, `/lists`, `/help`

## Тесты

```bash
pytest
```
