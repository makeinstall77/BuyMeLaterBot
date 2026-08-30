from calendar import monthrange
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr

from core.schemas import RRULE_BY_PRESET, RecurrencePreset

PRESET_LABELS: dict[RecurrencePreset, str] = {
    RecurrencePreset.daily: "Ежедневно",
    RecurrencePreset.weekdays: "По будням",
    RecurrencePreset.weekly: "Еженедельно",
    RecurrencePreset.monthly: "Ежемесячно",
}

WEEKDAY_TO_BYDAY = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
BYDAY_TO_WEEKDAY = {code: i for i, code in enumerate(WEEKDAY_TO_BYDAY)}
BYDAY_LABELS = {
    "MO": "пн",
    "TU": "вт",
    "WE": "ср",
    "TH": "чт",
    "FR": "пт",
    "SA": "сб",
    "SU": "вс",
}


def rrule_for_preset(
    preset: RecurrencePreset,
    due_at: datetime,
    *,
    byday: str | None = None,
    monthday: int | None = None,
) -> str:
    if preset == RecurrencePreset.weekly:
        code = byday or WEEKDAY_TO_BYDAY[due_at.weekday()]
        return f"FREQ=WEEKLY;BYDAY={code}"
    if preset == RecurrencePreset.monthly:
        day = monthday or due_at.day
        return f"FREQ=MONTHLY;BYMONTHDAY={day}"
    return RRULE_BY_PRESET[preset]


def preset_from_rrule(rrule: str | None) -> RecurrencePreset | None:
    if not rrule:
        return None
    if rrule == RRULE_BY_PRESET[RecurrencePreset.daily] or rrule.startswith("FREQ=DAILY"):
        return RecurrencePreset.daily
    if RRULE_BY_PRESET[RecurrencePreset.weekdays] in rrule or rrule == RRULE_BY_PRESET[RecurrencePreset.weekdays]:
        return RecurrencePreset.weekdays
    if rrule.startswith("FREQ=WEEKLY"):
        return RecurrencePreset.weekly
    if rrule.startswith("FREQ=MONTHLY"):
        return RecurrencePreset.monthly
    return None


def format_recurrence(item, timezone: str) -> str:
    if not item.is_recurring or not item.rrule:
        return "нет"
    label = format_rrule_label(item.rrule, item.is_recurring)
    return label or "да"


def format_rrule_label(rrule: str | None, is_recurring: bool = True) -> str | None:
    if not is_recurring or not rrule:
        return None
    preset = preset_from_rrule(rrule)
    if preset == RecurrencePreset.weekly:
        for code, label in BYDAY_LABELS.items():
            if f"BYDAY={code}" in rrule and "MO,TU" not in rrule:
                return f"{PRESET_LABELS[preset]} ({label})"
    if preset == RecurrencePreset.monthly and "BYMONTHDAY=" in rrule:
        day = rrule.split("BYMONTHDAY=", 1)[1].split(";")[0]
        return f"{PRESET_LABELS[preset]} ({day}-го)"
    if preset is not None:
        return PRESET_LABELS[preset]
    return None


def next_due_at(
    timezone: str,
    hour: int,
    minute: int,
    *,
    weekday: int | None = None,
    monthday: int | None = None,
    on_date: date | None = None,
    weekdays_only: bool = False,
    now: datetime | None = None,
) -> datetime:
    tz = ZoneInfo(timezone)
    now = now or datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)
    else:
        now = now.astimezone(tz)

    if on_date is not None:
        due = datetime(on_date.year, on_date.month, on_date.day, hour, minute, tzinfo=tz)
        if due <= now:
            due += timedelta(days=1)
        return due

    if weekday is not None:
        days_ahead = (weekday - now.weekday()) % 7
        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=days_ahead)
        if due <= now:
            due += timedelta(days=7)
        return due

    if monthday is not None:
        def _date_for(year: int, month: int) -> datetime:
            last = monthrange(year, month)[1]
            day = min(monthday, last)
            return datetime(year, month, day, hour, minute, tzinfo=tz)

        due = _date_for(now.year, now.month)
        if due <= now:
            if now.month == 12:
                due = _date_for(now.year + 1, 1)
            else:
                due = _date_for(now.year, now.month + 1)
        return due

    due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if due <= now:
        due += timedelta(days=1)
    if weekdays_only:
        while due.weekday() >= 5:
            due += timedelta(days=1)
    return due


def next_notify_after(rrule: str, dtstart: datetime, after: datetime) -> datetime | None:
    rule = rrulestr(rrule, dtstart=dtstart)
    return rule.after(after, inc=False)


def initial_next_notify(
    due_at: datetime,
    rrule: str,
    *,
    now: datetime | None = None,
) -> datetime:
    now = now or datetime.now(due_at.tzinfo or ZoneInfo("UTC"))
    if due_at > now:
        return due_at
    nxt = next_notify_after(rrule, due_at, now)
    return nxt if nxt is not None else due_at


def sync_rrule_on_due_change(due_at: datetime | None, rrule: str | None) -> str | None:
    if due_at is None or rrule is None:
        return rrule
    preset = preset_from_rrule(rrule)
    if preset == RecurrencePreset.weekly:
        return rrule_for_preset(preset, due_at)
    return rrule
