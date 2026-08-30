from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from bot.recurrence_edit import sync_recurring_after_due_change
from core.crud import update_item
from core.models import Item
from core.nlp.datetime_extract import extract_datetime, format_due
from core.recurrence import initial_next_notify
from core.schemas import ItemUpdate


def preset_due(preset: str, timezone: str) -> datetime | None:
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)

    if preset == "today09":
        due = now.replace(hour=9, minute=0, second=0, microsecond=0)
        return due if due > now else due + timedelta(days=1)

    if preset == "today17":
        due = now.replace(hour=17, minute=0, second=0, microsecond=0)
        return due if due > now else due + timedelta(days=1)

    if preset == "tomorrow09":
        due = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        return due

    if preset == "plus1h":
        return now + timedelta(hours=1)

    return None


async def apply_due_at(
    session: AsyncSession,
    item: Item,
    due_at: datetime | None,
    *,
    enable_notify: bool = True,
) -> Item:
    if due_at is None:
        notifications_enabled = False
    elif enable_notify and not notifications_enabled:
        notifications_enabled = True

    updates: dict = {
        "due_at": due_at,
        "notifications_enabled": notifications_enabled,
    }
    if due_at is None:
        updates["next_notify_at"] = None
        if item.is_recurring:
            updates["is_recurring"] = False
            updates["rrule"] = None
    elif notifications_enabled:
        if item.is_recurring and item.rrule:
            updates["next_notify_at"] = initial_next_notify(due_at, item.rrule)
        else:
            updates["next_notify_at"] = due_at

    item = await update_item(session, item, ItemUpdate(**updates))
    if due_at is None:
        return item
    return await sync_recurring_after_due_change(session, item)


async def apply_due_from_text(
    session: AsyncSession,
    item: Item,
    text: str,
    timezone: str,
) -> tuple[Item | None, str | None]:
    due_at, _ = extract_datetime(text.strip(), timezone)
    if due_at is None:
        return None, "Не удалось распознать дату. Пример: «завтра в 17:00» или «01.09.2026 09:00»"
    item = await apply_due_at(session, item, due_at)
    return item, None


def due_changed_message(item: Item, timezone: str) -> str:
    return f"📅 Дата обновлена: {format_due(item.due_at, timezone)}"
