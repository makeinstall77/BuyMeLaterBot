from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import main_menu_kb
from bot.views import render_list_message
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
    await message.answer(HELP_TEXT, reply_markup=main_menu_kb())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=main_menu_kb())


@router.message(Command("lists"))
async def cmd_lists(message: Message) -> None:
    await message.answer("Выберите список:", reply_markup=main_menu_kb())


@router.message(Command("shopping"))
async def cmd_shopping(
    message: Message, session: AsyncSession, scope: Scope
) -> None:
    text, kb = await render_list_message(session, scope, ListType.shopping)
    await message.answer(text, reply_markup=kb)


@router.message(Command("tasks"))
async def cmd_tasks(message: Message, session: AsyncSession, scope: Scope) -> None:
    text, kb = await render_list_message(session, scope, ListType.tasks)
    await message.answer(text, reply_markup=kb)
