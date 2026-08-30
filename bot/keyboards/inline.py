from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from core.models import Item, ListType


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
                InlineKeyboardButton(text=notify_label, callback_data=f"item:notify:{item.id}"),
                InlineKeyboardButton(text="« К списку", callback_data=f"menu:{list_type.value}"),
            ],
        ]
    )


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
