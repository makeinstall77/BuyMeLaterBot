# BuyMeLaterBot

Telegram-бот для семейных списков покупок и дел с REST API для Home Assistant.

## Стек

- Python 3.12, aiogram 3, FastAPI, SQLAlchemy 2 async
- PostgreSQL
- Yargy + dateparser для русскоязычных напоминаний
- APScheduler для уведомлений

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

## Docker

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

Команды: `/start`, `/shopping`, `/tasks`, `/lists`, `/settings`, `/link`, `/help`

## Home Assistant

Скопировать `homeassistant/custom_components/buymelater/` в `/config/custom_components/buymelater/`, перезагрузить HA и добавить интеграцию.

- Сайдбар **BuyMeLater** — вкладки Покупки/Дела, фильтр Мои/Групповые, CRUD
- Lovelace-карточка:

```yaml
type: custom:buymelater-card
title: Покупки
list_type: shopping
```

Опции: `list_id`, `entity` (todo.*), `list_type: shopping|tasks`. Если ничего не задано — все списки.

## Тесты

```bash
pytest
```
