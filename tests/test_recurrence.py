from datetime import datetime
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from bot.add_wizard import parse_clock
from core.recurrence import (
    format_rrule_label,
    initial_next_notify,
    next_due_at,
    next_notify_after,
    rrule_for_preset,
)
from core.schemas import RecurrencePreset


@freeze_time("2026-08-30 10:00:00", tz_offset=3)
def test_daily_next_after_notification() -> None:
    tz = ZoneInfo("Europe/Moscow")
    due_at = datetime(2026, 8, 30, 9, 0, tzinfo=tz)
    rrule = rrule_for_preset(RecurrencePreset.daily, due_at)
    now = datetime(2026, 8, 30, 9, 5, tzinfo=tz)
    nxt = next_notify_after(rrule, due_at, now)
    assert nxt is not None
    assert nxt.day == 31
    assert nxt.hour == 9


@freeze_time("2026-08-30 10:00:00", tz_offset=3)
def test_weekly_rrule_uses_due_weekday() -> None:
    tz = ZoneInfo("Europe/Moscow")
    due_at = datetime(2026, 9, 1, 17, 0, tzinfo=tz)  # Tuesday
    assert rrule_for_preset(RecurrencePreset.weekly, due_at) == "FREQ=WEEKLY;BYDAY=TU"


@freeze_time("2026-08-30 10:00:00", tz_offset=3)
def test_initial_next_notify_future_due() -> None:
    tz = ZoneInfo("Europe/Moscow")
    due_at = datetime(2026, 8, 30, 17, 0, tzinfo=tz)
    rrule = rrule_for_preset(RecurrencePreset.daily, due_at)
    nxt = initial_next_notify(due_at, rrule)
    assert nxt == due_at


@freeze_time("2026-08-30 18:00:00", tz_offset=3)
def test_initial_next_notify_past_due_daily() -> None:
    tz = ZoneInfo("Europe/Moscow")
    due_at = datetime(2026, 8, 30, 17, 0, tzinfo=tz)
    rrule = rrule_for_preset(RecurrencePreset.daily, due_at)
    nxt = initial_next_notify(due_at, rrule)
    assert nxt is not None
    assert nxt.day == 31
    assert nxt.hour == 17


@freeze_time("2026-08-30 10:00:00", tz_offset=10)
def test_next_due_weekly_wednesday() -> None:
    due = next_due_at("Asia/Vladivostok", 9, 0, weekday=2)
    assert due.weekday() == 2
    assert due.hour == 9
    assert due.day == 2  # Sep 2 2026 is Wednesday


@freeze_time("2026-08-30 10:00:00", tz_offset=10)
def test_next_due_monthly_day15() -> None:
    due = next_due_at("Asia/Vladivostok", 18, 0, monthday=15)
    assert due.day == 15
    assert due.month == 9
    assert due.hour == 18


def test_parse_clock() -> None:
    assert parse_clock("09:00") == (9, 0)
    assert parse_clock("17") == (17, 0)
    assert parse_clock("не время") is None


def test_format_rrule_label_weekly() -> None:
    label = format_rrule_label("FREQ=WEEKLY;BYDAY=WE", True)
    assert label == "Еженедельно (ср)"


def test_format_rrule_label_monthly() -> None:
    label = format_rrule_label("FREQ=MONTHLY;BYMONTHDAY=15", True)
    assert label == "Ежемесячно (15-го)"
