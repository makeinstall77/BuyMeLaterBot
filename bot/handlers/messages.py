from aiogram import F, Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.handlers.callbacks import store_pending
from bot.keyboards.inline import confirm_parsed_kb, main_menu_kb
from bot.views import render_list_message
from core.models import Scope, TelegramUser
from core.nlp.datetime_extract import format_due
from core.nlp.parser import parse_reminder

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

    parsed = parse_reminder(message.text or "", timezone=db_user.timezone)
    if parsed is None:
        return

    due_text = format_due(parsed.due_at, db_user.timezone)
    list_label = "🛒 Покупки" if parsed.list_type.value == "shopping" else "📋 Дела"
    notify = "вкл" if parsed.notifications_enabled else "выкл"

    store_pending(
        message.from_user.id,
        {"parsed": parsed},
    )

    await message.answer(
        f"Распознано:\n"
        f"• Список: {list_label}\n"
        f"• Задача: {parsed.title}\n"
        f"• Когда: {due_text}\n"
        f"• Уведомление: {notify}",
        reply_markup=confirm_parsed_kb(parsed.list_type),
    )
