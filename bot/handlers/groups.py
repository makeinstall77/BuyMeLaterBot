from aiogram import Router
from aiogram.types import ChatMemberUpdated
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.crud import get_or_create_scope

router = Router(name="groups")


@router.my_chat_member()
async def bot_added_to_group(event: ChatMemberUpdated, session: AsyncSession) -> None:
    if event.chat.type not in ("group", "supergroup"):
        return
    new_status = event.new_chat_member.status
    if new_status not in ("member", "administrator"):
        return

    scope = await get_or_create_scope(
        session,
        event.chat,
        default_timezone=settings.default_timezone,
        title=event.chat.title,
    )
    if event.new_chat_member.status == "member":
        await event.bot.send_message(
            event.chat.id,
            f"Привет! Веду общий список «{scope.title}».\n"
            "Напишите, например: «напомни купить хлеб в 17:00»",
        )
