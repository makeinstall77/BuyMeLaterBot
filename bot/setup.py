from aiogram import Dispatcher

from bot.handlers import callbacks, commands, groups, messages
from bot.middlewares.db import DbSessionMiddleware, ScopeMiddleware


def setup_dispatcher(dp: Dispatcher) -> None:
    dp.update.middleware(DbSessionMiddleware())
    dp.message.middleware(ScopeMiddleware())
    dp.callback_query.middleware(ScopeMiddleware())
    dp.my_chat_member.middleware(DbSessionMiddleware())

    dp.include_router(commands.router)
    dp.include_router(callbacks.router)
    dp.include_router(messages.router)
    dp.include_router(groups.router)
