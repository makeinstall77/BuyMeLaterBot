import re
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from bot.due_edit import apply_due_at
from bot.recurrence_edit import apply_recurrence_preset
from bot.state import get_wizard, pop_wizard, update_wizard
from core.models import Item
from core.recurrence import BYDAY_TO_WEEKDAY, next_due_at
from core.schemas import RecurrencePreset

_TIME_RE = re.compile(r"^(\d{1,2})[:\.](\d{2})$")
_HOUR_RE = re.compile(r"^(\d{1,2})$")


def parse_clock(text: str) -> tuple[int, int] | None:
    stripped = text.strip().lower().replace("в ", "")
    match = _TIME_RE.fullmatch(stripped)
    if match:
        hour, minute = int(match.group(1)), int(match.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return hour, minute
    match = _HOUR_RE.fullmatch(stripped)
    if match:
        hour = int(match.group(1))
        if 0 <= hour <= 23:
            return hour, 0
    return None


def period_prompt(preset: RecurrencePreset | None) -> str:
    if preset is None:
        return "Выберите дату:"
    if preset == RecurrencePreset.weekly:
        return "Выберите день недели:"
    if preset == RecurrencePreset.monthly:
        return "Выберите число месяца:"
    if preset == RecurrencePreset.daily:
        return "Выберите время (каждый день):"
    if preset == RecurrencePreset.weekdays:
        return "Выберите время (по будням):"
    return "Выберите время:"


async def finish_add_notify(
    session: AsyncSession,
    user_id: int,
    item: Item,
    hour: int,
    minute: int,
    timezone: str,
) -> Item:
    draft = get_wizard(user_id) or {}
    preset: RecurrencePreset | None = draft.get("preset")
    byday = draft.get("byday")
    monthday = draft.get("monthday")
    once_date = draft.get("once_date")

    weekday = BYDAY_TO_WEEKDAY.get(byday) if byday else None
    due_at = next_due_at(
        timezone,
        hour,
        minute,
        weekday=weekday,
        monthday=monthday,
        on_date=once_date,
        weekdays_only=preset == RecurrencePreset.weekdays,
    )
    item = await apply_due_at(session, item, due_at, enable_notify=True)
    if preset is not None:
        updated, error = await apply_recurrence_preset(
            session,
            item,
            preset,
            byday=byday,
            monthday=monthday,
        )
        if error is None and updated is not None:
            item = updated
    pop_wizard(user_id)
    return item


def today_or_tomorrow(timezone: str, which: str) -> date:
    tz = ZoneInfo(timezone)
    today = datetime_today(tz)
    if which == "tomorrow":
        return today + timedelta(days=1)
    return today


def datetime_today(tz) -> date:
    from datetime import datetime

    return datetime.now(tz).date()


def set_awaiting(user_id: int, awaiting: str | None) -> None:
    update_wizard(user_id, awaiting=awaiting)
