# BuyMeLaterBot — План реализации

## Обзор

Telegram-бот для семейных списков (покупки + дела) с периодическими/разовыми напоминаниями и кастомной интеграцией Home Assistant (HACS): `todo`-сущности + панель в левом сайдбаре.

**Источник истины:** PostgreSQL на отдельном хосте `postgres.example`; бэкенд (бот + API) — LXC на Proxmox.  
**Telegram** и **Home Assistant** — клиенты одного REST/WebSocket API.

---

## Инфраструктура (пример)

Целевая среда деплоя:

| Роль | Где | Доступ |
|------|-----|--------|
| **Proxmox (PVE)** | Хост виртуализации | `ssh proxmox.example` |
| **Home Assistant** | VM (HAOS) на Proxmox | Внешний UI: `https://homeassistant.example` (через reverse proxy) |
| **Home Assistant (внутри сети)** | та же VM HAOS | `ssh root@<ha-host>` |
| **BuyMeLaterBot** | LXC `<bot-host>` | API `http://<bot-host>:8080` |
| **PostgreSQL** | Общий хост для сервисов сети `<your-lan-subnet>` | `postgres.example` (`<postgres-host>:5432`) |

**Схема размещения:**

- Home Assistant — **VM с HAOS** под Proxmox (не LXC).
- Бот — **отдельный LXC** на Proxmox; Docker Compose внутри LXC (только приложение, без БД).
- PostgreSQL — **общий сервер** `postgres.example` для нескольких сервисов подсети `<your-lan-subnet>`. BuyMeLaterBot использует **отдельную БД** `buymelater` и пользователя `buymelater` (изоляция от других сервисов).
- HA обращается к API бота по **внутреннему IP LAN** (не через внешний URL HA).
- Telegram — **polling** из LXC наружу; публичный URL для бота не нужен.
- Порт API бота (8080) **не публикуется** через reverse proxy / DuckDNS.

**Типовые команды для администрирования:**

```bash
# Proxmox — создание/управление LXC
ssh proxmox.example

# Home Assistant — проверка доступности API бота из HAOS
ssh root@<ha-host>
curl -H "Authorization: Bearer $TOKEN" http://<bot-host>:8080/api/v1/scopes
```

---

## 1. Архитектура

```mermaid
flowchart TB
    subgraph telegram [Telegram]
        TGUser[Личный чат]
        TGGroup[Групповой чат]
    end

    subgraph lxc [LXC buymelater]
        Bot[aiogram Bot]
        API[FastAPI REST + WS]
        Scheduler[APScheduler]
    end

    subgraph pg [postgres.example]
        DB[(PostgreSQL)]
        DBBot[(buymelater DB)]
        DBOther[(другие БД сервисов)]
        DB --> DBBot
        DB --> DBOther
    end

    subgraph svcs [<your-lan-subnet>]
        OtherSvc[Другие сервисы]
    end

    subgraph haos [HAOS VM]
        HAInt[buymelater HA integration]
        Panel[Sidebar Panel JS]
        TodoEnt[todo.* entities]
    end

    TGUser --> Bot
    TGGroup --> Bot
    Bot --> API
    Scheduler --> API
    API --> DBBot
    Bot --> DBBot
    OtherSvc --> DBOther

    HAInt -->|HTTP LAN| API
    Panel -->|WebSocket via HA| HAInt
    HAInt --> TodoEnt
    Scheduler -->|notify| Bot
```

### Сетевая топология (Proxmox)

```mermaid
flowchart LR
    Internet -->|443| RevProxy[Reverse Proxy]
    RevProxy --> HAOS[HAOS VM]
    subgraph PVE[Proxmox proxmox.example]
        HAOS
        LXC[LXC buymelater-bot]
    end
    PG[postgres.example <postgres-host>]
    subgraph LAN [<your-lan-subnet>]
        LXC
        PG
        Other[другие сервисы]
    end
    HAOS -->|http://buymelater.lan:8080| LXC
    LXC -->|5432 buymelater| PG
    Other -->|5432| PG
    LXC -->|polling| Internet
```

| Компонент | Адрес | Назначение |
|-----------|-------|------------|
| HA внешний | `https://homeassistant.example` | UI, HACS, внешний доступ |
| HA внутренний | `ssh root@<ha-host>` | Отладка, внутренняя сеть |
| Bot API | `http://buymelater.lan:8080` (пример) | Только LAN, без публикации в интернет |
| PostgreSQL | `postgres.example` / `<postgres-host>:5432` | Общий инстанс; БД `buymelater` — только для этого бота |

**Рекомендация: polling, не webhook.**  
Бот в LXC не нуждается в публичном URL и TLS для Telegram. Polling проще, надёжнее за NAT/reverse proxy и не требует открывать порт для Telegram. Webhook имеет смысл только если позже появится публичный endpoint с валидным сертификатом.

---

## 2. Структура проекта

```
BuyMeLaterBot/
├── bot/                          # Telegram-бот
│   ├── __main__.py               # точка входа (polling)
│   ├── handlers/
│   │   ├── commands.py           # /start, /lists, /link
│   │   ├── callbacks.py          # inline-кнопки
│   │   ├── messages.py           # NL-парсинг свободного текста
│   │   └── groups.py             # добавление в группу, scope
│   ├── keyboards/                # InlineKeyboard builders
│   ├── middlewares/              # DB session, scope resolver
│   └── notifications.py          # отправка напоминаний
│
├── api/                          # FastAPI для HA и внутренних нужд
│   ├── main.py
│   ├── auth.py                   # Bearer token
│   ├── routes/
│   │   ├── lists.py
│   │   ├── items.py
│   │   ├── users.py
│   │   └── link.py               # привязка HA user ↔ Telegram
│   └── websocket.py              # push-обновления для HA panel
│
├── core/
│   ├── config.py                 # pydantic-settings
│   ├── db.py                     # SQLAlchemy async engine
│   ├── models.py                 # ORM-модели
│   ├── schemas.py                # Pydantic DTO
│   ├── crud.py                   # бизнес-логика
│   ├── scheduler.py              # APScheduler jobs
│   └── nlp/
│       ├── parser.py             # оркестратор: Yargy → dateparser
│       ├── grammar.py            # Yargy-правила: триггеры, тип списка, периодичность
│       └── datetime_extract.py   # dateparser + нормализация в UTC
│
├── alembic/                      # миграции БД
│
├── homeassistant/                # HACS custom integration
│   └── custom_components/
│       └── buymelater/
│           ├── manifest.json
│           ├── config_flow.py
│           ├── __init__.py
│           ├── coordinator.py    # DataUpdateCoordinator → REST API
│           ├── todo.py           # TodoListEntity per list
│           ├── websocket_api.py  # для panel
│           └── frontend/
│               └── buymelater-panel.js
│
├── deploy/
│   ├── docker-compose.yml
│   ├── Dockerfile
│   ├── .env.example
│   └── lxc-setup.md              # инструкция для Proxmox LXC
│
├── tests/
├── pyproject.toml
└── README.md
```

---

## 3. Модель данных

### 3.1 Scope (контекст списка)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID | PK |
| `scope_type` | enum | `personal` \| `group` |
| `telegram_chat_id` | bigint | ID чата Telegram |
| `title` | str | «Личный», «Семья», имя группы |
| `timezone` | str | IANA, default `Europe/Moscow` |

- **Личный:** `chat.type == private`, `telegram_chat_id == user.id`
- **Групповой:** `chat.type in (group, supergroup)`, один scope на группу

При добавлении бота в группу — автосоздание scope + приветственное сообщение.

### 3.2 TelegramUser

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID | PK |
| `telegram_user_id` | bigint | unique |
| `username` | str? | |
| `display_name` | str | |
| `timezone` | str | для NL-парсинга «в 17:00» |
| `ha_user_id` | str? | UUID HA user после /link |

### 3.3 List (список внутри scope)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID | PK |
| `scope_id` | FK | |
| `list_type` | enum | `shopping` \| `tasks` |
| `name` | str | «Покупки», «Дела» |

По умолчанию при создании scope — 2 списка: shopping + tasks.

### 3.4 Item (элемент списка)

| Поле | Тип | Описание |
|------|-----|----------|
| `id` | UUID | PK |
| `list_id` | FK | |
| `title` | str | «Купить хлеб» |
| `description` | text? | |
| `status` | enum | `active` \| `completed` \| `cancelled` |
| `created_by` | FK → TelegramUser | |
| `due_at` | timestamptz? | срок / время напоминания |
| `is_recurring` | bool | |
| `rrule` | str? | iCalendar RRULE, напр. `FREQ=DAILY;INTERVAL=1` |
| `notifications_enabled` | bool | |
| `last_notified_at` | timestamptz? | |
| `next_notify_at` | timestamptz? | индекс для scheduler |
| `completed_at` | timestamptz? | |

### 3.5 Периодичность (RRULE presets)

UI предлагает пресеты, в БД хранится RRULE:

| Пресет | RRULE |
|--------|-------|
| Ежедневно | `FREQ=DAILY` |
| По будням | `FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR` |
| Еженедельно | `FREQ=WEEKLY;BYDAY=MO` (день из due_at) |
| Ежемесячно | `FREQ=MONTHLY` |
| Каждые N дней | `FREQ=DAILY;INTERVAL=N` |

Для периодических: `next_notify_at` пересчитывается через `dateutil.rrule` после каждого срабатывания. Элемент остаётся `active` (не completed), пока пользователь не отключит периодичность или не удалит.

### 3.6 NotificationJob (опционально, фаза 2)

Отдельная таблица для отложенных одноразовых напоминаний, если нужна гибкость «напомнить за 1 час до».

---

## 4. Telegram-бот

### 4.1 Команды

| Команда | Действие |
|---------|----------|
| `/start` | Приветствие, регистрация пользователя, главное меню |
| `/lists` | Показать списки текущего scope |
| `/shopping` | Список покупок |
| `/tasks` | Список дел |
| `/add` | Мастер добавления (inline) |
| `/link <код>` | Привязка к HA (код из config flow) |
| `/settings` | Часовой пояс, уведомления по умолчанию |
| `/help` | Примеры фраз |

### 4.2 Inline UI (основной UX)

**Главное меню:**
```
[🛒 Покупки] [📋 Дела]
[➕ Добавить] [⚙️ Настройки]
```

**Карточка элемента:**
```
🛒 Купить хлеб
📅 сегодня 17:00 | 🔔 вкл
[✅ Готово] [✏️ Изменить] [🗑 Удалить]
[🔔 Выкл] [🔁 Периодичность]
```

**Редактирование (callback wizard):**
- Изменить текст
- Изменить дату/время (кнопки: сегодня, завтра, выбрать дату)
- Вкл/выкл уведомления
- Вкл/выкл периодичность → выбор пресета
- Перенести в другой список (shopping ↔ tasks)

### 4.3 Natural Language Parsing (Yargy + dateparser)

**Решение:** гибрид двух библиотек — не «или/или», а разделение ответственности.

| Задача | Библиотека | Почему |
|--------|------------|--------|
| Распознать команду-напоминание | **Yargy** | Морфология русского: «напомни», «напомните», «добавь» — одно правило через `morph_pipeline` |
| Тип списка (покупки / дела) | **Yargy** | «купить», «купи», «в список покупок» — явные грамматики |
| Периодичность в тексте | **Yargy** | «каждый день», «по будням», «каждую неделю» → RRULE-пресет |
| Дата и время | **dateparser** | «в 17:00», «завтра», «01.09.2026 в 09:00», «через 2 часа» |
| Заголовок задачи | **Yargy + вырезание** | Текст минус matched spans (триггер, дата, периодичность) |

#### Почему не только dateparser

- В групповом чате dateparser срабатывает на любую дату в сообщении → ложные срабатывания.
- Regex/списки ключевых слов не покрывают словоформы («напомните», «купи», «добавьте»).
- Периодичность («каждый понедельник») dateparser не извлекает структурно.

#### Почему не только Yargy

- Natasha `DatesExtractor` (Yargy) хорош для формальных дат («9 мая 2017»), но слаб на относительных («завтра», «через час», «в 17:00»).
- dateparser покрывает именно этот класс выражений из коробки.
- Альтернатива `russian-datetime-extractor` (тоже Yargy) — мощнее для русского, но менее поддерживается; dateparser проще в интеграции.

#### Алгоритм (`core/nlp/parser.py`)

```python
# 1. Yargy: есть ли команда?
match = reminder_parser.find(text)
if not match:
    return None  # игнор (в группе — только при триггере)

# 2. Yargy fact: list_type, recurrence_preset, matched spans
fact = match.fact  # ReminderCommand(list_type='shopping', recurrence='daily', ...)

# 3. dateparser: извлечь datetime из текста (минус spans Yargy)
remainder = remove_spans(text, match.spans)
dates = dateparser.search_dates(
    remainder,
    languages=['ru'],
    settings={
        'TIMEZONE': user.timezone,
        'RETURN_AS_TIMEZONE_AWARE': True,
        'PREFER_DATES_FROM': 'future',
    },
)
due_at = dates[0][1] if dates else None

# 4. title = remainder без дат, trimmed
title = clean_title(remainder, dates)

# 5. Собрать ParsedReminder → подтверждение с inline-кнопками
```

#### Yargy-грамматика (`core/nlp/grammar.py`)

```python
ReminderCommand = fact('ReminderCommand', ['list_type', 'recurrence'])

TRIGGER = morph_pipeline(['напомни', 'напоминание', 'добавь', 'не забудь'])
SHOPPING = morph_pipeline(['купить', 'купи', 'в список покупок'])
RECURRENCE = or_(
    rule(caseless('каждый'), caseless('день')).interpretation(...),
    rule(morph_pipeline(['по будням'])).interpretation(...),
    rule(morph_pipeline(['каждую неделю'])).interpretation(...),
)

REMINDER = rule(
    TRIGGER,
    optional(SHOPPING).interpretation(ReminderCommand.list_type.const('shopping')),
    ...
).interpretation(ReminderCommand)
```

Полный набор правил расширяется по мере появления новых фраз в `/help`.

#### Примеры

```
"напомни купить хлеб в 17:00"
→ Yargy: trigger + shopping
→ dateparser: today 17:00
→ shopping, title="хлеб", due_at=today 17:00, notify=on

"напомни записаться к стоматологу 01.09.2026 в 09:00"
→ Yargy: trigger, list_type=tasks (default)
→ dateparser: 2026-09-01 09:00
→ tasks, title="записаться к стоматологу"

"напомни каждый день полить цветы в 20:00"
→ Yargy: trigger + recurrence=daily
→ dateparser: today 20:00 (first occurrence)
→ tasks, title="полить цветы", rrule=FREQ=DAILY, notify=on
```

#### Зависимости NLP

```
yargy>=0.16          # правила + pymorphy2 (транзитивно)
dateparser>=1.2      # относительные/абсолютные даты
```

Не тянуть полный пакет `natasha` (NER, syntax, embeddings) — только `yargy`. При необходимости формальных дат можно переиспользовать грамматику `natasha.grammars.date` точечно.

#### Тестирование

- Юнит-тесты Yargy-правил: `tests/test_grammar.py` — таблица фраз → expected fact.
- Юнит-тесты dateparser: `tests/test_datetime_extract.py` — с `freezegun` для «сегодня/завтра».
- Интеграционные: `tests/test_parser.py` — end-to-end фразы из `/help`.

### 4.4 Scope resolution (middleware)

```python
def resolve_scope(chat, user) -> Scope:
    if chat.type == "private":
        return get_or_create_personal_scope(user.telegram_user_id)
    return get_or_create_group_scope(chat.id)
```

Все CRUD-операции привязаны к scope текущего чата.

### 4.5 Уведомления

- APScheduler проверяет `items WHERE notifications_enabled AND next_notify_at <= now()` каждые 30 сек
- Отправка в `scope.telegram_chat_id` (личный или групповой)
- Формат: «🔔 Напоминание: {title}» + inline [✅ Готово] [⏰ Отложить]
- После отправки: recurring → пересчитать `next_notify_at`; one-time → `notifications_enabled=False`

### 4.6 Голосовые сообщения (STT) — опционально

Telegram присылает voice/audio как **OGG Opus**. После транскрибации текст идёт в тот же пайплайн Yargy + dateparser (§4.3).

#### Сравнение движков

| | **Vosk** | **Faster-Whisper** |
|---|----------|-------------------|
| RAM (runtime) | ~300 MB (`small-ru-0.22`) | ~1–1.5 GB (`tiny`/`base`, int8, CPU) |
| Модель на диске | 45 MB | 75–150 MB |
| Точность (RU) | WER ~20–30% (small) | Значительно выше |
| Latency (10–30 сек аудио) | ~0.2–1 сек | ~2–10 сек на CPU |
| Offline | ✓ | ✓ |
| GPU | не нужен | опционально ускоряет |
| Telegram + aiogram | много готовых примеров | работает, но тяжелее |
| **512 MB LXC** (бот без БД) | ✓ достаточно для бота | ✗ не влезет |
| **1 GB LXC** | ✓ с Vosk | ✓ `tiny` int8 возможен |
| **2 GB LXC** | ✓ с запасом | ✓ комфортно (`small`) |

#### Рекомендация

**Фаза 1–2:** без STT (только текст).  
**Фаза 2.5 (опционально): Vosk** — оптимален для вашего LXC:
- `vosk-model-small-ru-0.22` (45 MB, Apache 2.0)
- `ffmpeg` для конвертации OGG → WAV 16 kHz mono
- STT в `asyncio.to_thread()` / `ProcessPoolExecutor`, чтобы не блокировать aiogram
- LXC бота **512 MB** достаточно без STT; **1024 MB** — если добавить Vosk

**Faster-Whisper** — если нужна высокая точность:
- **1 GB LXC** бота достаточно для `tiny-int8` (PostgreSQL уже вынесен)
- **2 GB LXC** — для модели `small` на CPU
- параметры: `WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=1)`

#### Пайплайн

```python
async def handle_voice(message: Message):
    ogg_path = await download_voice(message)
    wav_path = await to_thread(convert_ogg_to_wav, ogg_path)  # ffmpeg
    text = await to_thread(transcribe_vosk, wav_path)
    if not text.strip():
        await message.reply("Не разобрал голосовое, попробуйте текстом")
        return
    reminder = parse_reminder(text, user)  # тот же Yargy + dateparser
    ...
```

#### Улучшение точности Vosk

- Ограниченная грамматика (`SetGrammar`) со словами: «напомни», «купить», «завтра», числа — для режима «только команды»
- Fine-tune / custom model — overkill для MVP
- Показывать пользователю распознанный текст + [✅ Ок] [✏️ Исправить] перед сохранением

#### Зависимости (опционально)

```
vosk>=0.3
# faster-whisper>=1.0  # альтернатива, если ≥2 GB RAM
```

Системные: `ffmpeg` в Docker-образе.

---

## 5. REST API (для HA)

Base URL: `http://buymelater.lan:8080/api/v1`  
Auth: `Authorization: Bearer <API_TOKEN>` (один токен на инстанс, генерируется при установке)

### Endpoints

| Method | Path | Описание |
|--------|------|----------|
| GET | `/scopes` | Все scope (фильтр: `?type=personal\|group`) |
| GET | `/scopes/{id}/lists` | Списки scope |
| GET | `/lists/{id}/items` | Элементы (`?status=active`) |
| POST | `/lists/{id}/items` | Создать |
| PATCH | `/items/{id}` | Обновить |
| DELETE | `/items/{id}` | Удалить |
| POST | `/link/request` | HA запрашивает код привязки |
| POST | `/link/confirm` | Бот подтверждает (telegram /link) |
| GET | `/users/linked` | Список привязанных HA↔TG |
| WS | `/ws` | События: `item_created`, `item_updated`, `item_deleted` |

### Синхронизация

- HA `DataUpdateCoordinator` polling каждые 30 с
- WebSocket push для panel (мгновенное обновление UI)
- Конфликты: last-write-wins по `updated_at` (добавить поле)

---

## 6. Home Assistant интеграция (HACS)

### 6.1 Установка

1. Скопировать `homeassistant/custom_components/buymelater/` в `/config/custom_components/buymelater/` на HAOS
2. Перезагрузить HA → Настройки → Устройства → Добавить интеграцию → «BuyMeLater»
3. Config flow:
   - URL API: `http://buymelater.lan:8080`
   - API Token
   - Тест соединения
4. Для каждого HA-пользователя (опционально): «Привязать Telegram» → показать код → `/link <код>` в боте

### 6.2 Todo-сущности

На каждый `List` в API создаётся `TodoListEntity`:

| Entity ID | Пример | Видимость |
|-----------|--------|-----------|
| `todo.buymelater_semeja_pokupki` | Группа «Семья» — Покупки | Все |
| `todo.buymelater_semeja_dela` | Группа «Семья» — Дела | Все |
| `todo.buymelater_user_pokupki` | Личный пользователь — Покупки | Только привязанный HA user |
| `todo.buymelater_user_dela` | Личный пользователь — Дела | Только привязанный HA user |

**Личные списки в HA:** через `entity_registry` + `user_ids` (HA 2024+) или условное отображение в panel по `hass.user.id` ↔ `ha_user_id`. Нативные `todo`-карточки Lovelace покажут все entity — для приватности личные entity можно не добавлять на общие дашборды; panel фильтрует по текущему пользователю.

`TodoListEntity` реализует:
- `async_create_todo_item` → POST API
- `async_update_todo_item` → PATCH API
- `async_delete_todo_items` → DELETE API
- `SET_DUE_DATETIME_ON_ITEM` — due date из API
- `SET_DESCRIPTION_ON_ITEM` — description (RRULE, notify status в description или custom attributes)

### 6.3 Sidebar Panel

Регистрация через `panel_custom.async_register_panel`:
- URL: `/buymelater`
- Icon: `mdi:cart-check`
- Title: «BuyMeLater»

Panel (Lit/web component):
- Вкладки: «Покупки» | «Дела»
- Фильтр: «Мои» | «Групповые»
- Список с чекбоксами, датами, иконкой 🔔/🔁
- Кнопки: добавить, редактировать, удалить
- WebSocket к HA → `buymelater` websocket_api → прокси к bot API

Преимущество panel над чистыми `todo`-карточками: полный контроль над periodicity, notifications, фильтрацией по пользователю.

---

## 7. Деплой на Proxmox LXC

> См. также раздел [Инфраструктура (пример)](#инфраструктура-пример).

### 7.0 PostgreSQL (postgres.example) — общий сервер

`<postgres-host>` — **общий PostgreSQL** для сервисов подсети `<your-lan-subnet>`. Каждый сервис получает **свою БД и своего пользователя**; таблицы между сервисами не шарятся.

#### BuyMeLaterBot — создание БД и пользователя

```bash
ssh postgres.example   # или ssh root@<postgres-host>

sudo -u postgres psql <<'SQL'
CREATE USER buymelater WITH PASSWORD 'CHANGE_ME_STRONG';
CREATE DATABASE buymelater OWNER buymelater;
REVOKE ALL ON DATABASE buymelater FROM PUBLIC;
GRANT ALL PRIVILEGES ON DATABASE buymelater TO buymelater;
-- права на schema public (PostgreSQL 15+)
\c buymelater
GRANT ALL ON SCHEMA public TO buymelater;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO buymelater;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO buymelater;
SQL
```

Другие сервисы — аналогично: `CREATE USER service_x`, `CREATE DATABASE service_x OWNER service_x`.

#### pg_hba.conf

Доступ из внутренней подсети (все сервисы `<your-lan-subnet>`):

```
# TYPE  DATABASE    USER          ADDRESS           METHOD
host    buymelater  buymelater    <your-lan-subnet>    scram-sha-256
host    all         all           <your-lan-subnet>    scram-sha-256
```

Вторую строку можно заменить отдельными правилами per-database/per-user, если нужна более жёсткая сегментация. Пользователь `buymelater` всё равно видит только БД `buymelater` (нет прав на чужие БД).

#### postgresql.conf

- `listen_addresses = '*'` или IP интерфейса в `<your-lan-subnet>`
- При росте числа сервисов: `max_connections` с запасом; у каждого сервиса свой pool (SQLAlchemy `pool_size=5`)

#### Миграции Alembic

- Только БД `buymelater`; не трогают другие базы на том же инстансе
- `DATABASE_URL` указывает на `.../buymelater`

#### Проверка

```bash
# с любого хоста в <your-lan-subnet> (LXC бота, dev-машина)
psql "postgresql://buymelater:PASSWORD@postgres.example:5432/buymelater" -c 'SELECT 1'
```

#### Бэкапы (общий сервер)

- `pg_dump buymelater` — только наша БД
- `pg_dumpall` или поочерёдный dump всех БД — на уровне администрирования `postgres.example`

### 7.1 Создание LXC

```bash
# На proxmox.example
pct create 120 local:vztmpl/debian-12-standard_*.tar.zst \
  --hostname buymelater \
  --memory 512 --cores 1 --rootfs local-lvm:8 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --features nesting=1

pct start 120
pct enter 120
```

Зафиксировать IP в подсети `<your-lan-subnet>` (DHCP reservation или static), напр. `<bot-host>` → DNS `buymelater.lan`.

### 7.2 Установка в LXC

```bash
apt update && apt install -y docker.io docker-compose-plugin
git clone <your-repo-url> /opt/buymelater
cd /opt/buymelater/deploy
cp .env.example .env
# Заполнить: TELEGRAM_BOT_TOKEN, API_TOKEN, DATABASE_URL
docker compose up -d
```

`DATABASE_URL` в `.env`:
```
DATABASE_URL=postgresql+asyncpg://buymelater:PASSWORD@postgres.example:5432/buymelater
```

### 7.3 docker-compose.yml (скелет)

```yaml
services:
  app:
    build: ..
    ports: ["8080:8080"]
    environment:
      DATABASE_URL: ${DATABASE_URL}
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      API_TOKEN: ${API_TOKEN}
    restart: unless-stopped
    extra_hosts:
      - "postgres.example:<postgres-host>"  # если DNS не резолвится внутри контейнера
```

Один контейнер `app` запускает и FastAPI, и aiogram polling (через `asyncio.gather` в `__main__.py`).

### 7.4 Доступ из HAOS

На HAOS VM бот доступен по внутреннему IP LXC (подсеть `<your-lan-subnet>` или маршрутизируемая из HAOS):
```
http://<bot-host>:8080
```

Проверка с HAOS:
```bash
ssh root@<ha-host>
curl -H "Authorization: Bearer $TOKEN" http://<bot-host>:8080/api/v1/scopes
```

Firewall: порт 8080 только из LAN (HAOS + админ), **не** публиковать через внешний reverse proxy.

### 7.5 Бэкапы

- `pg_dump buymelater` на `postgres.example` по cron (только наша БД)
- Полный бэкап инстанса PG — ответственность админа `postgres.example`
- `.env` на LXC бота — вне git, бэкап отдельно

---

## 8. Безопасность

| Риск | Митигация |
|------|-----------|
| Утечка Telegram token | `.env`, не в git; права 600 |
| Несанкционированный доступ к API | Bearer token; API только в LAN |
| Подмена при /link | Одноразовый код, TTL 10 мин |
| Доступ к PostgreSQL | `pg_hba.conf`: `<your-lan-subnet>`; отдельный user/DB `buymelater` — без доступа к чужим базам |
| SQL injection | SQLAlchemy ORM, параметризованные запросы |
| Спам в группе | NL-парсинг только при ключевых словах; опция «только для админов» (фаза 2) |

---

## 9. Фазы реализации

### Фаза 1 — MVP (1–2 недели)

- [ ] Docker + подключение к PostgreSQL (`postgres.example`) + SQLAlchemy models + Alembic
- [ ] CRUD items, scopes (personal/group)
- [ ] Telegram: /start, /shopping, /tasks, inline списки
- [ ] Добавление/удаление/выполнение через кнопки
- [ ] NL-парсинг базовый («напомни … в HH:MM», «… DD.MM.YYYY»)
- [ ] Одноразовые напоминания (APScheduler)
- [ ] REST API: scopes, lists, items (read/write)

**Результат:** рабочий бот в Telegram, списки в личке и группе.

### Фаза 2 — Периодичность и редактирование (1 неделя)

- [ ] RRULE presets, toggle periodicity
- [ ] Редактирование: текст, дата, уведомления (inline wizard)
- [ ] Уведомления для recurring
- [ ] /settings (timezone)

### Фаза 3 — Home Assistant (1–2 недели)

- [ ] HACS custom integration: config flow, coordinator
- [ ] `todo.*` entities для групповых списков
- [ ] Привязка пользователей (/link + config flow)
- [ ] Личные `todo.*` entities per linked user
- [ ] Sidebar panel (базовый CRUD)

### Фаза 4 — Polish (ongoing)

- [ ] WebSocket push в panel
- [ ] «Отложить» напоминание
- [ ] Lovelace card (опционально)
- [ ] CI (pytest, ruff, mypy)
- [ ] Документация deploy/lxc-setup.md

---

## 10. Технологический стек

| Слой | Технология |
|------|------------|
| Язык | Python 3.12+ |
| Telegram | aiogram 3.x |
| API | FastAPI + uvicorn |
| ORM | SQLAlchemy 2.0 async |
| DB | PostgreSQL 16 (общий: `postgres.example`, БД `buymelater`) |
| Миграции | Alembic |
| Scheduler | APScheduler 3.x |
| NLP команды | yargy (ru, morph_pipeline) |
| NLP даты | dateparser (ru) |
| RRULE | python-dateutil |
| Config | pydantic-settings |
| HA | Python integration + panel_custom JS |
| Deploy | Docker Compose в LXC |

---

## 11. Первые шаги после утверждения плана

1. Инициализировать `pyproject.toml`, зависимости, `.env.example`
2. Создать модели и первую миграцию Alembic
3. Реализовать `core/crud.py` + тесты
4. Минимальный бот: /start + список покупок
5. `deploy/docker-compose.yml` + проверка в LXC
6. Параллельно: скелет HA integration
