from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.crud import get_or_create_scope, get_or_create_user
from core.db import async_session_factory
from core.events import WS_EVENTS_KEY


def _extract_chat_user(event: TelegramObject) -> tuple[Any, Any] | tuple[None, None]:
    if isinstance(event, Message):
        return event.chat, event.from_user
    if isinstance(event, CallbackQuery) and event.message is not None:
        return event.message.chat, event.from_user
    return None, None


class DbSessionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with async_session_factory() as session:
            data["session"] = session
            try:
                result = await handler(event, data)
                events = list(session.info.get(WS_EVENTS_KEY, []))
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            if events:
                from api.websocket import ws_manager

                for event_name, payload in events:
                    await ws_manager.broadcast(event_name, payload)
            return result


class ScopeMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        chat, user = _extract_chat_user(event)
        if chat is None or user is None:
            return await handler(event, data)

        session: AsyncSession = data["session"]
        db_user = await get_or_create_user(session, user, settings.default_timezone)
        scope = await get_or_create_scope(
            session,
            chat,
            default_timezone=db_user.timezone,
            title=chat.full_name if chat.type == "private" else chat.title,
        )
        data["db_user"] = db_user
        data["scope"] = scope
        return await handler(event, data)
