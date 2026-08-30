from sqlalchemy.ext.asyncio import AsyncSession

from core.crud import update_item
from core.models import Item
from core.recurrence import (
    format_recurrence,
    initial_next_notify,
    rrule_for_preset,
    sync_rrule_on_due_change,
)
from core.schemas import ItemUpdate, RecurrencePreset


async def apply_recurrence_preset(
    session: AsyncSession,
    item: Item,
    preset: RecurrencePreset,
) -> tuple[Item | None, str | None]:
    if item.due_at is None:
        return None, "Сначала укажите дату (кнопка «📅 Дата»)"

    rrule = rrule_for_preset(preset, item.due_at)
    next_at = initial_next_notify(item.due_at, rrule)

    item = await update_item(
        session,
        item,
        ItemUpdate(
            is_recurring=True,
            rrule=rrule,
            notifications_enabled=True,
            next_notify_at=next_at,
        ),
    )
    return item, None


async def clear_recurrence(session: AsyncSession, item: Item) -> Item:
    next_at = item.due_at if item.notifications_enabled and item.due_at else None
    return await update_item(
        session,
        item,
        ItemUpdate(
            is_recurring=False,
            rrule=None,
            next_notify_at=next_at,
        ),
    )


def recurrence_changed_message(item: Item, timezone: str) -> str:
    label = format_recurrence(item, timezone)
    return f"🔁 Периодичность: {label}"


async def sync_recurring_after_due_change(session: AsyncSession, item: Item) -> Item:
    if not item.is_recurring or item.due_at is None or not item.rrule:
        return item

    rrule = sync_rrule_on_due_change(item.due_at, item.rrule)
    next_at = (
        initial_next_notify(item.due_at, rrule)
        if item.notifications_enabled
        else None
    )
    return await update_item(
        session,
        item,
        ItemUpdate(rrule=rrule, next_notify_at=next_at),
    )
