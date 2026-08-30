from datetime import datetime
from zoneinfo import ZoneInfo

from freezegun import freeze_time

from core.recurrence import initial_next_notify, next_notify_after, rrule_for_preset
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
