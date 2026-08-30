from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil.rrule import rrulestr

from core.schemas import RRULE_BY_PRESET, RecurrencePreset

PRESET_LABELS: dict[RecurrencePreset, str] = {
    RecurrencePreset.daily: "Ежедневно",
    RecurrencePreset.weekdays: "По будням",
    RecurrencePreset.weekly: "Еженедельно",
    RecurrencePreset.monthly: "Ежемесячно",
}

_WEEKDAY_TO_BYDAY = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")


def rrule_for_preset(preset: RecurrencePreset, due_at: datetime) -> str:
    if preset == RecurrencePreset.weekly:
        byday = _WEEKDAY_TO_BYDAY[due_at.weekday()]
        return f"FREQ=WEEKLY;BYDAY={byday}"
    return RRULE_BY_PRESET[preset]


def preset_from_rrule(rrule: str | None) -> RecurrencePreset | None:
    if not rrule:
        return None
    for preset, template in RRULE_BY_PRESET.items():
        if preset != RecurrencePreset.weekly and rrule == template:
            return preset
    if rrule.startswith("FREQ=WEEKLY") and "BYDAY=" in rrule:
        return RecurrencePreset.weekly
    return None


def format_recurrence(item, timezone: str) -> str:
    if not item.is_recurring or not item.rrule:
        return "нет"
    preset = preset_from_rrule(item.rrule)
    if preset is not None:
        return PRESET_LABELS[preset]
    return "да"


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
