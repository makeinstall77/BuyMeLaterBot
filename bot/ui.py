from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

_last: dict[tuple[int, int], int] = {}


async def _delete(bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramBadRequest:
        return


def _key(chat_id: int, user_id: int) -> tuple[int, int]:
    return (chat_id, user_id)


async def show_screen(
    event: CallbackQuery | Message,
    text: str,
    reply_markup=None,
    *,
    delete_user: bool = False,
) -> None:
    if isinstance(event, CallbackQuery):
        if event.from_user is None or event.message is None:
            return
        user_id = event.from_user.id
        chat_id = event.message.chat.id
        bot = event.bot
        key = _key(chat_id, user_id)
        try:
            if reply_markup is None:
                await event.message.edit_text(text)
            else:
                await event.message.edit_text(text, reply_markup=reply_markup)
            _last[key] = event.message.message_id
            return
        except TelegramBadRequest:
            pass
    else:
        if event.from_user is None:
            return
        user_id = event.from_user.id
        chat_id = event.chat.id
        bot = event.bot
        key = _key(chat_id, user_id)
        if delete_user:
            await _delete(bot, chat_id, event.message_id)

    prev = _last.get(key)
    if prev is not None:
        await _delete(bot, chat_id, prev)
    sent = await bot.send_message(chat_id, text, reply_markup=reply_markup)
    _last[key] = sent.message_id
