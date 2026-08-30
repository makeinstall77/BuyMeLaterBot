import asyncio
import logging

import uvicorn
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from api.main import app
from bot.notifications import send_item_notification
from bot.setup import setup_dispatcher
from core.config import settings
from core.scheduler import NotificationScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    setup_dispatcher(dp)

    async def notify_callback(session, item) -> None:
        await send_item_notification(bot, session, item)

    scheduler = NotificationScheduler(notify_callback)
    scheduler.start()

    config = uvicorn.Config(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )
    server = uvicorn.Server(config)

    logger.info("Starting API on %s:%s", settings.api_host, settings.api_port)
    logger.info("Starting Telegram bot polling")

    try:
        await asyncio.gather(server.serve(), dp.start_polling(bot))
    finally:
        scheduler.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
