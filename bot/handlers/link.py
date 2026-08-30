from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.ui import show_screen
from core.crud import link_ha_user
from core.link import consume_link_code
from core.models import TelegramUser

router = Router(name="link")


@router.message(Command("link"))
async def cmd_link(message: Message, session: AsyncSession, db_user: TelegramUser) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await show_screen(
            message,
            "Привязка к Home Assistant.\n\n"
            "В HA: Настройки → BuyMeLater → «Привязать Telegram»\n"
            "Затем отправьте сюда:\n/link КОД",
            delete_user=True,
        )
        return

    ha_user_id = consume_link_code(parts[1])
    if ha_user_id is None:
        await show_screen(
            message,
            "Код не найден или истёк. Запросите новый в Home Assistant.",
            delete_user=True,
        )
        return

    await link_ha_user(session, db_user, ha_user_id)
    await show_screen(message, "✅ Telegram привязан к Home Assistant.", delete_user=True)
