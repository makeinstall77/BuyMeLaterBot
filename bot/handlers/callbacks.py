from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import back_to_list_kb, item_actions_kb, list_type_kb, main_menu_kb
from bot.views import format_item_card, render_list_message
from core.crud import complete_item, delete_item, get_item, get_list_by_type, update_item
from core.models import ListType, Scope, TelegramUser
from core.schemas import ItemUpdate

router = Router(name="callbacks")

_pending_parsed: dict[int, dict] = {}


def store_pending(user_id: int, data: dict) -> None:
    _pending_parsed[user_id] = data


def pop_pending(user_id: int) -> dict | None:
    return _pending_parsed.pop(user_id, None)


@router.callback_query(F.data == "menu:home")
async def cb_menu_home(callback: CallbackQuery) -> None:
    await callback.message.edit_text("Выберите список:", reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def cb_menu_help(callback: CallbackQuery) -> None:
    from bot.handlers.commands import HELP_TEXT

    await callback.message.edit_text(HELP_TEXT, reply_markup=main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:add")
async def cb_menu_add(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выберите тип списка или напишите фразу с «напомни»:",
        reply_markup=list_type_kb(),
    )
    await callback.answer()


@router.callback_query(F.data.in_({"menu:shopping", "add:shopping"}))
async def cb_shopping(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    text, kb = await render_list_message(session, scope, ListType.shopping)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.in_({"menu:tasks", "add:tasks"}))
async def cb_tasks(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    text, kb = await render_list_message(session, scope, ListType.tasks)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("item:view:"))
async def cb_item_view(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    item_id = UUID(callback.data.split(":")[2])
    item = await get_item(session, item_id)
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    list_type = item.list.list_type
    text = format_item_card(item, list_type, scope.timezone)
    await callback.message.edit_text(
        text, reply_markup=item_actions_kb(item, list_type)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("item:done:"))
async def cb_item_done(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    item_id = UUID(callback.data.split(":")[2])
    item = await get_item(session, item_id)
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    list_type = item.list.list_type
    await complete_item(session, item)
    text, kb = await render_list_message(session, scope, list_type)
    await callback.message.edit_text(f"✅ Готово: {item.title}\n\n{text}", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("item:del:"))
async def cb_item_del(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    item_id = UUID(callback.data.split(":")[2])
    item = await get_item(session, item_id)
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    list_type = item.list.list_type
    title = item.title
    await delete_item(session, item)
    text, kb = await render_list_message(session, scope, list_type)
    await callback.message.edit_text(f"🗑 Удалено: {title}\n\n{text}", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("item:notify:"))
async def cb_item_notify(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    item_id = UUID(callback.data.split(":")[2])
    item = await get_item(session, item_id)
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    new_state = not item.notifications_enabled
    if new_state and item.due_at is None:
        await callback.answer("Сначала укажите дату в тексте сообщения", show_alert=True)
        return
    await update_item(
        session,
        item,
        ItemUpdate(
            notifications_enabled=new_state,
            next_notify_at=item.due_at if new_state else None,
        ),
    )
    list_type = item.list.list_type
    text = format_item_card(item, list_type, scope.timezone)
    await callback.message.edit_text(text, reply_markup=item_actions_kb(item, list_type))
    await callback.answer("Уведомления обновлены")


@router.callback_query(F.data.startswith("parsed:ok:"))
async def cb_parsed_ok(
    callback: CallbackQuery,
    session: AsyncSession,
    scope: Scope,
    db_user: TelegramUser,
) -> None:
    pending = pop_pending(callback.from_user.id)
    if pending is None:
        await callback.answer("Нечего сохранять", show_alert=True)
        return

    from core.crud import create_item
    from core.schemas import ItemCreate

    parsed = pending["parsed"]
    list_type = ListType(callback.data.split(":")[2])
    db_list = await get_list_by_type(session, scope.id, list_type)
    if db_list is None:
        await callback.answer("Список не найден", show_alert=True)
        return

    from core.nlp.parser import recurrence_to_rrule

    item = await create_item(
        session,
        db_list.id,
        ItemCreate(
            title=parsed.title,
            due_at=parsed.due_at,
            notifications_enabled=parsed.notifications_enabled,
            is_recurring=parsed.is_recurring,
            rrule=recurrence_to_rrule(parsed),
            created_by_id=db_user.id,
        ),
    )
    text, kb = await render_list_message(session, scope, list_type)
    await callback.message.edit_text(
        f"✅ Добавлено: {item.title}\n\n{text}",
        reply_markup=kb,
    )
    await callback.answer()


@router.callback_query(F.data == "parsed:cancel")
async def cb_parsed_cancel(callback: CallbackQuery) -> None:
    pop_pending(callback.from_user.id)
    await callback.message.edit_text("Отменено.", reply_markup=main_menu_kb())
    await callback.answer()
