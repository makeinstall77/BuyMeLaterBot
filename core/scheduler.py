import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.crud import get_due_notifications, mark_notified
from core.db import async_session_factory

logger = logging.getLogger(__name__)


class NotificationScheduler:
    def __init__(self, send_callback) -> None:
        self._send_callback = send_callback
        self._scheduler = AsyncIOScheduler(timezone=UTC)

    def start(self) -> None:
        self._scheduler.add_job(self._process_due, "interval", seconds=30, id="notifications")
        self._scheduler.start()
        logger.info("Notification scheduler started")

    def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    async def _process_due(self) -> None:
        now = datetime.now(UTC)
        async with async_session_factory() as session:
            items = await get_due_notifications(session, now)
            for item in items:
                try:
                    await self._send_callback(session, item)
                    await mark_notified(session, item, now=now)
                except Exception:
                    logger.exception("Failed to send notification for item %s", item.id)
            if items:
                await session.commit()
