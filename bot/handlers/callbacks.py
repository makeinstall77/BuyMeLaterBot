from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.add_wizard import finish_add_notify, period_prompt, set_awaiting, today_or_tomorrow
from bot.keyboards.inline import (
    add_monthday_kb,
    add_notify_kb,
    add_once_date_kb,
    add_recurrence_kb,
    add_time_kb,
    add_weekday_kb,
    item_actions_kb,
    list_back_kb,
    list_type_kb,
    main_menu_kb,
)
from bot.state import (
    clear_add_wizard,
    pop_pending_parsed,
    set_pending_add,
    set_pending_add_recur,
    store_pending_parsed,
    update_wizard,
)
from bot.ui import show_screen
from bot.views import (
    add_title_prompt,
    format_item_card,
    open_list_screen,
    render_list_message,
)
from core.crud import complete_item, delete_item, get_item, get_list_by_type, update_item
from core.models import ListType, Scope, TelegramUser
from core.recurrence import initial_next_notify
from core.schemas import ItemUpdate, RecurrencePreset

router = Router(name="callbacks")


def store_pending(user_id: int, data: dict) -> None:
    store_pending_parsed(user_id, data)


def pop_pending(user_id: int) -> dict | None:
    return pop_pending_parsed(user_id)


@router.callback_query(F.data == "menu:home")
async def cb_menu_home(callback: CallbackQuery) -> None:
    clear_add_wizard(callback.from_user.id)
    await show_screen(callback, "Выберите список:", main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:help")
async def cb_menu_help(callback: CallbackQuery) -> None:
    from bot.handlers.commands import HELP_TEXT

    await show_screen(callback, HELP_TEXT, main_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "menu:add")
async def cb_menu_add(callback: CallbackQuery) -> None:
    await show_screen(
        callback,
        "Выберите тип списка или напишите фразу с «напомни»:",
        list_type_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "menu:shopping")
async def cb_shopping(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    clear_add_wizard(callback.from_user.id)
    text, kb = await open_list_screen(
        session, scope, ListType.shopping, callback.from_user.id
    )
    await show_screen(callback, text, kb)
    await callback.answer()


@router.callback_query(F.data == "menu:tasks")
async def cb_tasks(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    clear_add_wizard(callback.from_user.id)
    text, kb = await open_list_screen(session, scope, ListType.tasks, callback.from_user.id)
    await show_screen(callback, text, kb)
    await callback.answer()


@router.callback_query(F.data.startswith("list:view:"))
async def cb_list_view(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    list_type = ListType(callback.data.split(":")[2])
    clear_add_wizard(callback.from_user.id)
    text, kb = await open_list_screen(
        session, scope, list_type, callback.from_user.id, auto_add_if_empty=False
    )
    await show_screen(callback, text, kb)
    await callback.answer()


@router.callback_query(F.data.startswith("list:add:"))
async def cb_list_add(callback: CallbackQuery) -> None:
    list_type = ListType(callback.data.split(":")[2])
    set_pending_add(callback.from_user.id, list_type)
    await show_screen(callback, add_title_prompt(list_type), list_back_kb(list_type))
    await callback.answer()


@router.callback_query(F.data.in_({"add:shopping", "add:tasks"}))
async def cb_add_type(callback: CallbackQuery) -> None:
    list_type = ListType.shopping if callback.data == "add:shopping" else ListType.tasks
    set_pending_add(callback.from_user.id, list_type)
    await show_screen(callback, add_title_prompt(list_type), list_type_kb())
    await callback.answer()


async def _prompt_add(
    callback: CallbackQuery,
    item,
    scope: Scope,
    extra: str,
    kb,
) -> None:
    await show_screen(
        callback,
        f"{format_item_card(item, item.list.list_type, scope.timezone)}\n\n{extra}",
        kb,
    )


@router.callback_query(F.data.startswith("add:asknotify:"))
async def cb_add_ask_notify(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    item = await get_item(session, UUID(callback.data.split(":")[2]))
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    await _prompt_add(callback, item, scope, "Включить напоминание?", add_notify_kb(item.id))
    await callback.answer()


@router.callback_query(F.data.startswith("add:notify:"))
async def cb_add_notify(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    await callback.answer()
    _, _, answer, item_id_str = callback.data.split(":", 3)
    item = await get_item(session, UUID(item_id_str))
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return

    if answer == "no":
        clear_add_wizard(callback.from_user.id)
        list_type = item.list.list_type
        await show_screen(callback, format_item_card(item, list_type, scope.timezone), item_actions_kb(item, list_type))
        return

    set_pending_add_recur(callback.from_user.id, item.id, None)
    await _prompt_add(callback, item, scope, "Выберите периодичность:", add_recurrence_kb(item.id))


@router.callback_query(F.data.startswith("add:period:"))
async def cb_add_period(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    item = await get_item(session, UUID(callback.data.split(":")[2]))
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    await _prompt_add(callback, item, scope, "Выберите периодичность:", add_recurrence_kb(item.id))
    await callback.answer()


@router.callback_query(F.data.startswith("add:recur:"))
async def cb_add_recur(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    _, _, item_id_str, preset_str = callback.data.split(":", 3)
    item = await get_item(session, UUID(item_id_str))
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return

    preset = None
    if preset_str != "once":
        try:
            preset = RecurrencePreset(preset_str)
        except ValueError:
            await callback.answer("Неизвестный пресет", show_alert=True)
            return

    set_pending_add_recur(callback.from_user.id, item.id, preset)
    if preset == RecurrencePreset.weekly:
        kb = add_weekday_kb(item.id)
    elif preset == RecurrencePreset.monthly:
        kb = add_monthday_kb(item.id)
    elif preset is None:
        kb = add_once_date_kb(item.id)
    else:
        set_awaiting(callback.from_user.id, "time")
        kb = add_time_kb(item.id)

    await _prompt_add(callback, item, scope, period_prompt(preset), kb)
    await callback.answer()


@router.callback_query(F.data.startswith("add:wday:"))
async def cb_add_wday(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    _, _, item_id_str, byday = callback.data.split(":", 3)
    item = await get_item(session, UUID(item_id_str))
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    update_wizard(callback.from_user.id, item_id=item.id, preset=RecurrencePreset.weekly, byday=byday, awaiting="time")
    await _prompt_add(callback, item, scope, "Выберите время:", add_time_kb(item.id))
    await callback.answer()


@router.callback_query(F.data.startswith("add:mday:"))
async def cb_add_mday(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    _, _, item_id_str, day_str = callback.data.split(":", 3)
    item = await get_item(session, UUID(item_id_str))
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    update_wizard(
        callback.from_user.id,
        item_id=item.id,
        preset=RecurrencePreset.monthly,
        monthday=int(day_str),
        awaiting="time",
    )
    await _prompt_add(callback, item, scope, "Выберите время:", add_time_kb(item.id))
    await callback.answer()


@router.callback_query(F.data.startswith("add:ondate:"))
async def cb_add_ondate(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    _, _, item_id_str, which = callback.data.split(":", 3)
    item = await get_item(session, UUID(item_id_str))
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    if which == "manual":
        update_wizard(callback.from_user.id, item_id=item.id, preset=None, awaiting="once_date")
        await _prompt_add(
            callback,
            item,
            scope,
            "Отправьте дату сообщением, например: завтра или 01.09.2026",
            add_once_date_kb(item.id),
        )
        await callback.answer()
        return

    once_date = today_or_tomorrow(scope.timezone, which)
    update_wizard(callback.from_user.id, item_id=item.id, preset=None, once_date=once_date, awaiting="time")
    await _prompt_add(callback, item, scope, "Выберите время:", add_time_kb(item.id))
    await callback.answer()


@router.callback_query(F.data.startswith("add:timetext:"))
async def cb_add_timetext(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    item = await get_item(session, UUID(callback.data.split(":")[2]))
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    set_awaiting(callback.from_user.id, "time")
    await _prompt_add(
        callback,
        item,
        scope,
        "Отправьте время сообщением, например: 09:00 или 17",
        add_time_kb(item.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("add:time:"))
async def cb_add_time(callback: CallbackQuery, session: AsyncSession, scope: Scope) -> None:
    _, _, item_id_str, hhmm = callback.data.split(":", 3)
    item = await get_item(session, UUID(item_id_str))
    if item is None:
        await callback.answer("Элемент не найден", show_alert=True)
        return
    hour, minute = int(hhmm[:2]), int(hhmm[2:])
    item = await finish_add_notify(session, callback.from_user.id, item, hour, minute, scope.timezone)
    list_type = item.list.list_type
    await show_screen(
        callback,
        f"✅ Напоминание настроено\n\n{format_item_card(item, list_type, scope.timezone)}",
        item_actions_kb(item, list_type),
    )
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
    await show_screen(callback, text, item_actions_kb(item, list_type))
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
    await show_screen(callback, f"✅ Готово: {item.title}\n\n{text}", kb)
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
    await show_screen(callback, f"🗑 Удалено: {title}\n\n{text}", kb)
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
        await callback.answer("Сначала укажите дату (кнопка «📅 Дата»)", show_alert=True)
        return
    next_at = None
    if new_state and item.due_at:
        if item.is_recurring and item.rrule:
            next_at = initial_next_notify(item.due_at, item.rrule)
        else:
            next_at = item.due_at
    await update_item(
        session,
        item,
        ItemUpdate(
            notifications_enabled=new_state,
            next_notify_at=next_at,
        ),
    )
    list_type = item.list.list_type
    text = format_item_card(item, list_type, scope.timezone)
    await show_screen(callback, text, item_actions_kb(item, list_type))
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
    await show_screen(callback, f"✅ Добавлено: {item.title}\n\n{text}", kb)
    await callback.answer()


@router.callback_query(F.data == "parsed:cancel")
async def cb_parsed_cancel(callback: CallbackQuery) -> None:
    pop_pending(callback.from_user.id)
    await show_screen(callback, "Отменено.", main_menu_kb())
    await callback.answer()
