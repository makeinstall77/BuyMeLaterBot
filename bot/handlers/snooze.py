from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.snooze import snooze_until
from bot.ui import show_screen
from bot.views import format_item_card
from core.crud import get_item, update_item
from core.models import Scope
from core.nlp.datetime_extract import format_due
from core.schemas import ItemUpdate

router = Router(name="snooze")

SNOOZE_LABELS = {
    "plus1h": "+1 час",
    "plus3h": "+3 часа",
    "tomorrow09": "завтра 09:00",
}


@router.callback_query(F.data.startswith("item:snooze:"))
async def cb_item_snooze(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    _, _, item_id_str, preset = callback.data.split(":", 3)
    item_id = UUID(item_id_str)
    item = await get_item(session, item_id)
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return

    until = snooze_until(preset, scope.timezone)
    if until is None:
        await callback.answer("Неизвестный пресет", show_alert=True)
        return

    await update_item(
        session,
        item,
        ItemUpdate(notifications_enabled=True, next_notify_at=until),
    )
    label = SNOOZE_LABELS.get(preset, preset)
    list_type = item.list.list_type
    text = format_item_card(item, list_type, scope.timezone)
    await show_screen(
        callback,
        f"⏰ Напоминание отложено до {format_due(until, scope.timezone)} ({label})\n\n{text}",
    )
    await callback.answer("Отложено")
