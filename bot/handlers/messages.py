from uuid import UUID

from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.add_wizard import finish_add_notify, parse_clock, set_awaiting
from bot.due_edit import apply_due_from_text, due_changed_message
from bot.handlers.due import apply_pending_add_recur
from bot.keyboards.inline import add_notify_kb, add_time_kb, confirm_parsed_kb, item_actions_kb
from bot.state import (
    get_pending_add,
    get_pending_due_edit,
    get_wizard,
    pop_pending_add,
    pop_pending_due_edit,
    set_pending_due_edit,
    store_pending_parsed,
    update_wizard,
)
from bot.ui import show_screen
from bot.views import format_item_card
from core.crud import create_item, get_item, get_list_by_type
from core.models import ListType, Scope, TelegramUser
from core.nlp.datetime_extract import extract_datetime, format_due
from core.nlp.parser import parse_reminder
from core.recurrence import PRESET_LABELS
from core.schemas import ItemCreate

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

    wizard = get_wizard(message.from_user.id)
    awaiting = wizard.get("awaiting") if wizard else None
    if awaiting == "once_date":
        await _handle_once_date_text(message, session, scope)
        return
    if awaiting == "time":
        await _handle_time_text(message, session, scope)
        return

    pending_item_id = get_pending_due_edit(message.from_user.id)
    if pending_item_id is not None:
        await _handle_due_text(message, session, scope, pending_item_id)
        return

    pending_list_type = get_pending_add(message.from_user.id)
    if pending_list_type is not None:
        await _handle_add_title(message, session, scope, db_user, pending_list_type)
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

    await show_screen(
        message,
        f"Распознано:\n"
        f"• Список: {list_label}\n"
        f"• Задача: {parsed.title}\n"
        f"• Когда: {due_text}\n"
        f"• Периодичность: {recur}\n"
        f"• Уведомление: {notify}",
        confirm_parsed_kb(parsed.list_type),
        delete_user=True,
    )


async def _handle_add_title(
    message: Message,
    session: AsyncSession,
    scope: Scope,
    db_user: TelegramUser,
    list_type: ListType,
) -> None:
    title = (message.text or "").strip()[:500]
    if not title:
        await show_screen(message, "Напишите название элемента.", delete_user=True)
        return

    db_list = await get_list_by_type(session, scope.id, list_type)
    if db_list is None:
        pop_pending_add(message.from_user.id)
        await show_screen(message, "Список не найден.", delete_user=True)
        return

    item = await create_item(
        session,
        db_list.id,
        ItemCreate(title=title, created_by_id=db_user.id),
    )
    pop_pending_add(message.from_user.id)
    await show_screen(
        message,
        f"✅ Добавлено: {item.title}\n\nВключить напоминание?",
        add_notify_kb(item.id),
        delete_user=True,
    )


async def _handle_once_date_text(message: Message, session: AsyncSession, scope: Scope) -> None:
    wizard = get_wizard(message.from_user.id) or {}
    item_id = wizard.get("item_id")
    item = await get_item(session, item_id) if item_id else None
    if item is None:
        await show_screen(message, "Элемент не найден.", delete_user=True)
        return
    due_at, _ = extract_datetime(message.text or "", scope.timezone)
    if due_at is None:
        await show_screen(
            message,
            f"{format_item_card(item, item.list.list_type, scope.timezone)}\n\n"
            "Не удалось распознать дату. Пример: завтра или 01.09.2026",
            add_time_kb(item.id),
            delete_user=True,
        )
        return
    update_wizard(message.from_user.id, once_date=due_at.date(), awaiting="time")
    await show_screen(
        message,
        f"{format_item_card(item, item.list.list_type, scope.timezone)}\n\nВыберите время:",
        add_time_kb(item.id),
        delete_user=True,
    )


async def _handle_time_text(message: Message, session: AsyncSession, scope: Scope) -> None:
    wizard = get_wizard(message.from_user.id) or {}
    item_id = wizard.get("item_id")
    item = await get_item(session, item_id) if item_id else None
    if item is None:
        await show_screen(message, "Элемент не найден.", delete_user=True)
        return
    parsed = parse_clock(message.text or "")
    if parsed is None:
        set_awaiting(message.from_user.id, "time")
        await show_screen(
            message,
            f"{format_item_card(item, item.list.list_type, scope.timezone)}\n\n"
            "Не удалось распознать время. Пример: 09:00 или 17",
            add_time_kb(item.id),
            delete_user=True,
        )
        return
    hour, minute = parsed
    item = await finish_add_notify(session, message.from_user.id, item, hour, minute, scope.timezone)
    list_type = item.list.list_type
    await show_screen(
        message,
        f"✅ Напоминание настроено\n\n{format_item_card(item, list_type, scope.timezone)}",
        item_actions_kb(item, list_type),
        delete_user=True,
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
        await show_screen(message, "Элемент не найден.", delete_user=True)
        return

    item, error = await apply_due_from_text(session, item, message.text or "", scope.timezone)
    if error:
        set_pending_due_edit(message.from_user.id, item_id)
        await show_screen(message, error, delete_user=True)
        return

    item = await apply_pending_add_recur(session, message.from_user.id, item)
    list_type = item.list.list_type
    text = format_item_card(item, list_type, scope.timezone)
    await show_screen(
        message,
        f"{due_changed_message(item, scope.timezone)}\n\n{text}",
        item_actions_kb(item, list_type),
        delete_user=True,
    )
