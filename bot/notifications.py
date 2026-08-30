from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Item
from core.nlp.datetime_extract import format_due


async def send_item_notification(
    bot,
    session: AsyncSession,
    item: Item,
) -> None:
    scope = item.list.scope
    due = format_due(item.due_at, scope.timezone)
    text = f"🔔 Напоминание: {item.title}\n📅 {due}"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Готово", callback_data=f"item:done:{item.id}"),
            ],
        ]
    )
    await bot.send_message(scope.telegram_chat_id, text, reply_markup=kb)
