from zoneinfo import ZoneInfo

from freezegun import freeze_time

from core.models import ListType
from core.nlp.parser import parse_reminder


@freeze_time("2026-08-30 10:00:00", tz_offset=3)
def test_parse_shopping_with_time() -> None:
    parsed = parse_reminder("напомни купить хлеб в 17:00", timezone="Europe/Moscow")
    assert parsed is not None
    assert parsed.list_type == ListType.shopping
    assert "хлеб" in parsed.title.lower()
    assert parsed.due_at is not None
    local = parsed.due_at.astimezone(ZoneInfo("Europe/Moscow"))
    assert local.hour == 17


@freeze_time("2026-08-30 10:00:00", tz_offset=3)
def test_parse_task_with_date() -> None:
    parsed = parse_reminder(
        "напомни записаться к стоматологу 01.09.2026 в 09:00",
        timezone="Europe/Moscow",
    )
    assert parsed is not None
    assert parsed.list_type == ListType.tasks
    assert parsed.due_at is not None
    local = parsed.due_at.astimezone(ZoneInfo("Europe/Moscow"))
    assert local.day == 1
    assert local.month == 9
    assert local.year == 2026


@freeze_time("2026-08-30 10:00:00", tz_offset=3)
def test_parse_recurring_daily() -> None:
    parsed = parse_reminder("напомни полить цветы каждый день в 09:00", timezone="Europe/Moscow")
    assert parsed is not None
    assert parsed.is_recurring is True
    assert parsed.recurrence is not None
    assert parsed.recurrence.value == "daily"


def test_ignore_plain_text() -> None:
    assert parse_reminder("привет как дела", timezone="Europe/Moscow") is None
