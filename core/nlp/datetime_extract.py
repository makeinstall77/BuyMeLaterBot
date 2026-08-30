import re
from datetime import datetime
from zoneinfo import ZoneInfo

from dateparser.search import search_dates

DATEPARSER_SETTINGS = {
    "RETURN_AS_TIMEZONE_AWARE": True,
    "PREFER_DATES_FROM": "future",
}

RU_DATE_TIME_RE = re.compile(
    r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{4})(?:\s+в\s+(\d{1,2}):(\d{2}))?",
    re.IGNORECASE,
)


def _parse_ru_explicit_date(text: str, timezone: str) -> tuple[datetime | None, str]:
    match = RU_DATE_TIME_RE.search(text)
    if not match:
        return None, text

    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    hour = int(match.group(4)) if match.group(4) else 9
    minute = int(match.group(5)) if match.group(5) else 0
    tz = ZoneInfo(timezone)
    due_at = datetime(year, month, day, hour, minute, tzinfo=tz)
    remainder = text[: match.start()] + " " + text[match.end() :]
    remainder = re.sub(r"\s+", " ", remainder).strip(" ,.-")
    return due_at, remainder


def extract_datetime(text: str, timezone: str) -> tuple[datetime | None, str]:
    explicit, remainder = _parse_ru_explicit_date(text, timezone)
    if explicit is not None:
        return explicit, remainder

    settings = {**DATEPARSER_SETTINGS, "TIMEZONE": timezone, "TO_TIMEZONE": timezone}
    matches = search_dates(text, languages=["ru"], settings=settings)
    if not matches:
        return None, text

    _, due_at = matches[0]
    remainder = text
    for fragment, _ in matches:
        remainder = remainder.replace(fragment, " ")
    remainder = re.sub(r"\s+", " ", remainder).strip(" ,.-")
    return due_at, remainder


def format_due(due_at: datetime | None, timezone: str) -> str:
    if due_at is None:
        return "без даты"
    local = due_at.astimezone(ZoneInfo(timezone))
    return local.strftime("%d.%m.%Y %H:%M")
