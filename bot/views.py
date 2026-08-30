from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Item, ListType, Scope
from core.nlp.datetime_extract import format_due
from core.recurrence import format_recurrence


def add_from_list_prompt(list_type: ListType) -> str:
    label = "покупки" if list_type == ListType.shopping else "дела"
    return (
        f"Список пуст.\n\n"
        f"Напишите название для «{label.capitalize()}».\n\n"
        "Пример: «Время поливать орхидеи»"
    )


def add_title_prompt(list_type: ListType) -> str:
    label = "покупки" if list_type == ListType.shopping else "дела"
    return (
        f"Напишите название для списка «{label.capitalize()}».\n\n"
        "Пример: «Время поливать орхидеи»"
    )


async def open_list_screen(
    session: AsyncSession,
    scope: Scope,
    list_type: ListType,
    user_id: int,
    *,
    auto_add_if_empty: bool = True,
) -> tuple[str, InlineKeyboardMarkup | None]:
    from bot.keyboards.inline import empty_list_kb, list_back_kb
    from bot.state import set_pending_add
    from core.crud import get_list_by_type, list_items

    db_list = await get_list_by_type(session, scope.id, list_type)
    if db_list is None:
        return "Список не найден.", None

    items = await list_items(session, db_list.id)
    icon = "🛒" if list_type == ListType.shopping else "📋"
    title = f"{icon} {db_list.name} — {scope.title}"

    if not items:
        if auto_add_if_empty:
            set_pending_add(user_id, list_type)
            return add_from_list_prompt(list_type), list_back_kb(list_type)
        return f"{title}\n\nПусто.", empty_list_kb(list_type)

    return await render_list_message(session, scope, list_type)


async def render_list_message(
    session: AsyncSession,
    scope: Scope,
    list_type: ListType,
) -> tuple[str, InlineKeyboardMarkup | None]:
    from bot.keyboards.inline import empty_list_kb, list_footer_kb
    from core.crud import get_list_by_type, list_items

    db_list = await get_list_by_type(session, scope.id, list_type)
    if db_list is None:
        return "Список не найден.", None

    items = await list_items(session, db_list.id)
    icon = "🛒" if list_type == ListType.shopping else "📋"
    title = f"{icon} {db_list.name} — {scope.title}"

    if not items:
        return f"{title}\n\nПусто.", empty_list_kb(list_type)

    lines = [title, ""]
    buttons: list[list[InlineKeyboardButton]] = []
    for item in items[:20]:
        due = format_due(item.due_at, scope.timezone)
        notify = "🔔" if item.notifications_enabled else ""
        recur = " 🔁" if item.is_recurring else ""
        lines.append(f"• {item.title}{recur} {notify}\n  📅 {due}")
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{'🛒' if list_type == ListType.shopping else '📋'} {item.title[:30]}",
                    callback_data=f"item:view:{item.id}",
                )
            ]
        )
    buttons.extend(list_footer_kb(list_type).inline_keyboard)
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


def format_item_card(item: Item, list_type: ListType, timezone: str) -> str:
    due = format_due(item.due_at, timezone)
    notify = "вкл" if item.notifications_enabled else "выкл"
    recurring = format_recurrence(item, timezone)
    return (
        f"{'🛒' if list_type == ListType.shopping else '📋'} {item.title}\n"
        f"📅 {due} | 🔔 {notify} | 🔁 {recurring}"
    )
