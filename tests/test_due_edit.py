from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from bot.due_edit import preset_due


@freeze_time("2026-08-30 10:00:00", tz_offset=3)
def test_preset_today17_future() -> None:
    due = preset_due("today17", "Europe/Moscow")
    assert due is not None
    local = due.astimezone(ZoneInfo("Europe/Moscow"))
    assert local.hour == 17
    assert local.day == 30


@freeze_time("2026-08-30 18:00:00", tz_offset=3)
def test_preset_today17_rolls_to_next_day() -> None:
    due = preset_due("today17", "Europe/Moscow")
    assert due is not None
    local = due.astimezone(ZoneInfo("Europe/Moscow"))
    assert local.day == 31
    assert local.hour == 17
