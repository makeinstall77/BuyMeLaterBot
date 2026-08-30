from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import main_menu_kb
from bot.state import clear_add_wizard
from bot.ui import show_screen
from bot.views import open_list_screen
from core.models import ListType, Scope

router = Router(name="commands")

HELP_TEXT = (
    "Привет! Я помогаю вести списки покупок и дел.\n\n"
    "Команды:\n"
    "/shopping — список покупок\n"
    "/tasks — список дел\n"
    "/lists — меню\n"
    "/settings — часовой пояс\n"
    "/link — привязка Home Assistant\n"
    "/help — эта справка\n\n"
    "Или просто напишите:\n"
    "• напомни купить хлеб в 17:00\n"
    "• напомни полить цветы каждый день в 09:00\n"
    "• напомни записаться к стоматологу 01.09.2026 в 09:00"
)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    if message.from_user:
        clear_add_wizard(message.from_user.id)
    await show_screen(message, HELP_TEXT, main_menu_kb(), delete_user=True)


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    if message.from_user:
        clear_add_wizard(message.from_user.id)
    await show_screen(message, HELP_TEXT, main_menu_kb(), delete_user=True)


@router.message(Command("lists"))
async def cmd_lists(message: Message) -> None:
    if message.from_user:
        clear_add_wizard(message.from_user.id)
    await show_screen(message, "Выберите список:", main_menu_kb(), delete_user=True)


@router.message(Command("shopping"))
async def cmd_shopping(
    message: Message, session: AsyncSession, scope: Scope
) -> None:
    if message.from_user:
        clear_add_wizard(message.from_user.id)
    text, kb = await open_list_screen(
        session, scope, ListType.shopping, message.from_user.id
    )
    await show_screen(message, text, kb, delete_user=True)


@router.message(Command("tasks"))
async def cmd_tasks(message: Message, session: AsyncSession, scope: Scope) -> None:
    if message.from_user:
        clear_add_wizard(message.from_user.id)
    text, kb = await open_list_screen(session, scope, ListType.tasks, message.from_user.id)
    await show_screen(message, text, kb, delete_user=True)
