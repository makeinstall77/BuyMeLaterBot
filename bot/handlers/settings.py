from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import settings_kb
from core.crud import update_scope_timezone, update_user_timezone
from core.models import Scope, TelegramUser

router = Router(name="settings")

TIMEZONE_LABELS = {
    "Europe/Moscow": "Москва (UTC+3)",
    "Europe/Kaliningrad": "Калининград (UTC+2)",
    "Asia/Yekaterinburg": "Екатеринбург (UTC+5)",
    "Asia/Novosibirsk": "Новосибирск (UTC+7)",
    "Asia/Vladivostok": "Владивосток (UTC+10)",
    "UTC": "UTC",
}


def _settings_text(db_user: TelegramUser, scope: Scope) -> str:
    user_tz = TIMEZONE_LABELS.get(db_user.timezone, db_user.timezone)
    scope_tz = TIMEZONE_LABELS.get(scope.timezone, scope.timezone)
    lines = [
        "⚙️ Настройки",
        "",
        f"Ваш часовой пояс: {user_tz}",
    ]
    if scope.scope_type.value == "group":
        lines.append(f"Часовой пояс группы: {scope_tz}")
    lines.append("")
    lines.append("Выберите часовой пояс для распознавания дат:")
    return "\n".join(lines)


@router.message(Command("settings"))
async def cmd_settings(message: Message, db_user: TelegramUser, scope: Scope) -> None:
    await message.answer(
        _settings_text(db_user, scope),
        reply_markup=settings_kb(db_user.timezone),
    )


@router.callback_query(F.data.startswith("settings:tz:"))
async def cb_settings_tz(
    callback: CallbackQuery,
    session: AsyncSession,
    db_user: TelegramUser,
    scope: Scope,
) -> None:
    timezone = callback.data.split(":", 2)[2]
    await update_user_timezone(session, db_user, timezone)
    if scope.scope_type.value == "personal":
        await update_scope_timezone(session, scope, timezone)

    label = TIMEZONE_LABELS.get(timezone, timezone)
    await callback.message.edit_text(
        f"✅ Часовой пояс: {label}\n\n{_settings_text(db_user, scope)}",
        reply_markup=settings_kb(timezone),
    )
    await callback.answer()
