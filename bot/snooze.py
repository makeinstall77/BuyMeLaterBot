from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def snooze_until(preset: str, timezone: str) -> datetime | None:
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)

    if preset == "plus1h":
        return now + timedelta(hours=1)
    if preset == "plus3h":
        return now + timedelta(hours=3)
    if preset == "tomorrow09":
        due = (now + timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=0)
        return due
    return None
