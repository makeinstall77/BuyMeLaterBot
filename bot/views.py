from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Item, ListType, Scope
from core.nlp.datetime_extract import format_due
from core.recurrence import format_recurrence


async def render_list_message(
    session: AsyncSession,
    scope: Scope,
    list_type: ListType,
) -> tuple[str, InlineKeyboardMarkup | None]:
    from core.crud import get_list_by_type, list_items

    db_list = await get_list_by_type(session, scope.id, list_type)
    if db_list is None:
        return "Список не найден.", None

    items = await list_items(session, db_list.id)
    icon = "🛒" if list_type == ListType.shopping else "📋"
    title = f"{icon} {db_list.name} — {scope.title}"

    if not items:
        text = f"{title}\n\nПусто. Напишите, например:\n«напомни купить хлеб в 17:00»"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="« Меню", callback_data="menu:home")]]
        )
        return text, kb

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
    buttons.append([InlineKeyboardButton(text="« Меню", callback_data="menu:home")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=buttons)


def format_item_card(item: Item, list_type: ListType, timezone: str) -> str:
    due = format_due(item.due_at, timezone)
    notify = "вкл" if item.notifications_enabled else "выкл"
    recurring = format_recurrence(item, timezone)
    return (
        f"{'🛒' if list_type == ListType.shopping else '📋'} {item.title}\n"
        f"📅 {due} | 🔔 {notify} | 🔁 {recurring}"
    )
