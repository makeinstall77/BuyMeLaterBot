from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.due_edit import apply_due_at, due_changed_message, preset_due
from bot.keyboards.inline import due_edit_kb, item_actions_kb
from bot.state import set_pending_due_edit
from bot.views import format_item_card
from core.crud import get_item
from core.models import Scope

router = Router(name="due")


@router.callback_query(F.data.startswith("due:menu:"))
async def cb_due_menu(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    item_id = UUID(callback.data.split(":")[2])
    item = await get_item(session, item_id)
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    list_type = item.list.list_type
    text = format_item_card(item, list_type, scope.timezone)
    await callback.message.edit_text(
        f"{text}\n\nВыберите новую дату и время:",
        reply_markup=due_edit_kb(item.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("due:set:"))
async def cb_due_set(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    _, _, item_id_str, preset = callback.data.split(":", 3)
    item_id = UUID(item_id_str)
    item = await get_item(session, item_id)
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return

    due_at = preset_due(preset, scope.timezone)
    if due_at is None:
        await callback.answer("Неизвестный пресет", show_alert=True)
        return

    item = await apply_due_at(session, item, due_at)
    list_type = item.list.list_type
    text = format_item_card(item, list_type, scope.timezone)
    await callback.message.edit_text(
        f"{due_changed_message(item, scope.timezone)}\n\n{text}",
        reply_markup=item_actions_kb(item, list_type),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("due:clear:"))
async def cb_due_clear(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    item_id = UUID(callback.data.split(":")[2])
    item = await get_item(session, item_id)
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return

    item = await apply_due_at(session, item, None, enable_notify=False)
    list_type = item.list.list_type
    text = format_item_card(item, list_type, scope.timezone)
    await callback.message.edit_text(text, reply_markup=item_actions_kb(item, list_type))
    await callback.answer("Дата удалена")


@router.callback_query(F.data.startswith("due:manual:"))
async def cb_due_manual(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    item_id = UUID(callback.data.split(":")[2])
    item = await get_item(session, item_id)
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return

    set_pending_due_edit(callback.from_user.id, item_id)
    await callback.message.edit_text(
        f"{'🛒' if item.list.list_type.value == 'shopping' else '📋'} {item.title}\n\n"
        "Отправьте дату и время сообщением, например:\n"
        "• завтра в 17:00\n"
        "• 01.09.2026 в 09:00\n"
        "• через 2 часа",
        reply_markup=due_edit_kb(item.id),
    )
    await callback.answer()
