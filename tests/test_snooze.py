from zoneinfo import ZoneInfo

from freezegun import freeze_time

from bot.snooze import snooze_until


@freeze_time("2026-08-30 10:00:00+0300")
def test_snooze_plus1h() -> None:
    until = snooze_until("plus1h", "Europe/Moscow")
    assert until is not None
    local = until.astimezone(ZoneInfo("Europe/Moscow"))
    assert local.hour == 11


@freeze_time("2026-08-30 10:00:00", tz_offset=3)
def test_snooze_tomorrow09() -> None:
    until = snooze_until("tomorrow09", "Europe/Moscow")
    assert until is not None
    local = until.astimezone(ZoneInfo("Europe/Moscow"))
    assert local.day == 31
    assert local.hour == 9
