from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.models import Item, ListType
from core.schemas import RecurrencePreset


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🛒 Покупки", callback_data="menu:shopping"),
                InlineKeyboardButton(text="📋 Дела", callback_data="menu:tasks"),
            ],
            [
                InlineKeyboardButton(text="➕ Добавить", callback_data="menu:add"),
                InlineKeyboardButton(text="ℹ️ Помощь", callback_data="menu:help"),
            ],
        ]
    )


def list_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🛒 Покупки", callback_data="add:shopping"),
                InlineKeyboardButton(text="📋 Дела", callback_data="add:tasks"),
            ],
            [InlineKeyboardButton(text="« Назад", callback_data="menu:home")],
        ]
    )


def item_actions_kb(item: Item, list_type: ListType) -> InlineKeyboardMarkup:
    notify_label = "🔔 Выкл" if item.notifications_enabled else "🔔 Вкл"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Готово", callback_data=f"item:done:{item.id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"item:del:{item.id}"),
            ],
            [
                InlineKeyboardButton(text="📅 Дата", callback_data=f"due:menu:{item.id}"),
                InlineKeyboardButton(text="🔁 Период", callback_data=f"recur:menu:{item.id}"),
            ],
            [
                InlineKeyboardButton(text=notify_label, callback_data=f"item:notify:{item.id}"),
            ],
            [
                InlineKeyboardButton(text="« К списку", callback_data=f"menu:{list_type.value}"),
            ],
        ]
    )


def due_edit_kb(item_id) -> InlineKeyboardMarkup:
    iid = str(item_id)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня 09:00", callback_data=f"due:set:{iid}:today09"),
                InlineKeyboardButton(text="Сегодня 17:00", callback_data=f"due:set:{iid}:today17"),
            ],
            [
                InlineKeyboardButton(text="Завтра 09:00", callback_data=f"due:set:{iid}:tomorrow09"),
                InlineKeyboardButton(text="+1 час", callback_data=f"due:set:{iid}:plus1h"),
            ],
            [
                InlineKeyboardButton(text="✏️ Ввести текстом", callback_data=f"due:manual:{iid}"),
                InlineKeyboardButton(text="🚫 Убрать дату", callback_data=f"due:clear:{iid}"),
            ],
            [InlineKeyboardButton(text="« Назад", callback_data=f"item:view:{iid}")],
        ]
    )


def settings_kb(current_tz: str) -> InlineKeyboardMarkup:
    zones = [
        ("Europe/Moscow", "Москва UTC+3"),
        ("Europe/Kaliningrad", "Калининград UTC+2"),
        ("Asia/Yekaterinburg", "Екатеринбург UTC+5"),
        ("Asia/Novosibirsk", "Новосибирск UTC+7"),
        ("Asia/Vladivostok", "Владивосток UTC+10"),
        ("UTC", "UTC"),
    ]
    rows = [
        [
            InlineKeyboardButton(
                text=f"{'✓ ' if tz == current_tz else ''}{label}",
                callback_data=f"settings:tz:{tz}",
            )
        ]
        for tz, label in zones
    ]
    rows.append([InlineKeyboardButton(text="« Меню", callback_data="menu:home")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def recurrence_kb(item_id) -> InlineKeyboardMarkup:
    iid = str(item_id)
    presets = [
        (RecurrencePreset.daily, "Ежедневно"),
        (RecurrencePreset.weekdays, "По будням"),
        (RecurrencePreset.weekly, "Еженедельно"),
        (RecurrencePreset.monthly, "Ежемесячно"),
    ]
    rows = [
        [
            InlineKeyboardButton(
                text=label,
                callback_data=f"recur:set:{iid}:{preset.value}",
            )
        ]
        for preset, label in presets
    ]
    rows.append(
        [
            InlineKeyboardButton(text="🚫 Выключить", callback_data=f"recur:clear:{iid}"),
            InlineKeyboardButton(text="« Назад", callback_data=f"item:view:{iid}"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_parsed_kb(list_type: ListType) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ок", callback_data=f"parsed:ok:{list_type.value}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="parsed:cancel"),
            ],
        ]
    )


def back_to_list_kb(list_type: ListType) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="« К списку", callback_data=f"menu:{list_type.value}")]]
    )
