from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import item_actions_kb, recurrence_kb
from bot.recurrence_edit import (
    apply_recurrence_preset,
    clear_recurrence,
    recurrence_changed_message,
)
from bot.views import format_item_card
from core.crud import get_item
from core.models import Scope
from core.schemas import RecurrencePreset

router = Router(name="recurrence")


@router.callback_query(F.data.startswith("recur:menu:"))
async def cb_recur_menu(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    item_id = UUID(callback.data.split(":")[2])
    item = await get_item(session, item_id)
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    list_type = item.list.list_type
    text = format_item_card(item, list_type, scope.timezone)
    await callback.message.edit_text(
        f"{text}\n\nВыберите периодичность:",
        reply_markup=recurrence_kb(item.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("recur:set:"))
async def cb_recur_set(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    _, _, item_id_str, preset_str = callback.data.split(":", 3)
    item_id = UUID(item_id_str)
    item = await get_item(session, item_id)
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return

    try:
        preset = RecurrencePreset(preset_str)
    except ValueError:
        await callback.answer("Неизвестный пресет", show_alert=True)
        return

    item, error = await apply_recurrence_preset(session, item, preset)
    if error:
        await callback.answer(error, show_alert=True)
        return

    list_type = item.list.list_type
    text = format_item_card(item, list_type, scope.timezone)
    await callback.message.edit_text(
        f"{recurrence_changed_message(item, scope.timezone)}\n\n{text}",
        reply_markup=item_actions_kb(item, list_type),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("recur:clear:"))
async def cb_recur_clear(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    item_id = UUID(callback.data.split(":")[2])
    item = await get_item(session, item_id)
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return

    item = await clear_recurrence(session, item)
    list_type = item.list.list_type
    text = format_item_card(item, list_type, scope.timezone)
    await callback.message.edit_text(
        f"{recurrence_changed_message(item, scope.timezone)}\n\n{text}",
        reply_markup=item_actions_kb(item, list_type),
    )
    await callback.answer("Периодичность выключена")
