from uuid import UUID

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.due_edit import apply_due_from_text, due_changed_message
from bot.keyboards.inline import confirm_parsed_kb, item_actions_kb
from bot.state import (
    get_pending_due_edit,
    pop_pending_due_edit,
    set_pending_due_edit,
    store_pending_parsed,
)
from bot.views import format_item_card
from core.crud import get_item
from core.models import Scope, TelegramUser
from core.nlp.datetime_extract import format_due
from core.nlp.parser import parse_reminder
from core.recurrence import PRESET_LABELS

router = Router(name="messages")


@router.message(F.text)
async def handle_text(
    message: Message,
    session: AsyncSession,
    scope: Scope,
    db_user: TelegramUser,
) -> None:
    if message.text and message.text.startswith("/"):
        return

    pending_item_id = get_pending_due_edit(message.from_user.id)
    if pending_item_id is not None:
        await _handle_due_text(message, session, scope, pending_item_id)
        return

    parsed = parse_reminder(message.text or "", timezone=db_user.timezone)
    if parsed is None:
        return

    due_text = format_due(parsed.due_at, db_user.timezone)
    list_label = "🛒 Покупки" if parsed.list_type.value == "shopping" else "📋 Дела"
    notify = "вкл" if parsed.notifications_enabled else "выкл"
    recur = PRESET_LABELS.get(parsed.recurrence, "нет") if parsed.recurrence else "нет"

    store_pending_parsed(
        message.from_user.id,
        {"parsed": parsed},
    )

    await message.answer(
        f"Распознано:\n"
        f"• Список: {list_label}\n"
        f"• Задача: {parsed.title}\n"
        f"• Когда: {due_text}\n"
        f"• Периодичность: {recur}\n"
        f"• Уведомление: {notify}",
        reply_markup=confirm_parsed_kb(parsed.list_type),
    )


async def _handle_due_text(
    message: Message,
    session: AsyncSession,
    scope: Scope,
    item_id: UUID,
) -> None:
    pop_pending_due_edit(message.from_user.id)
    item = await get_item(session, item_id)
    if item is None:
        await message.answer("Элемент не найден.")
        return

    item, error = await apply_due_from_text(session, item, message.text or "", scope.timezone)
    if error:
        set_pending_due_edit(message.from_user.id, item_id)
        await message.answer(error)
        return

    list_type = item.list.list_type
    text = format_item_card(item, list_type, scope.timezone)
    await message.answer(
        f"{due_changed_message(item, scope.timezone)}\n\n{text}",
        reply_markup=item_actions_kb(item, list_type),
    )
