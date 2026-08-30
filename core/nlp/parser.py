import re

from core.models import ListType
from core.nlp.datetime_extract import extract_datetime
from core.nlp.grammar import get_reminder_parser, has_reminder_trigger
from core.schemas import ParsedReminder, RRULE_BY_PRESET


def _clean_title(text: str) -> str:
    text = re.sub(r"^(напомни|напоминание|добавь|не забудь)\s*", "", text, flags=re.I)
    text = re.sub(r"^(купить|купи)\s*", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ,.-")
    return text


def parse_reminder(text: str, *, timezone: str) -> ParsedReminder | None:
    stripped = text.strip()
    if not stripped or not has_reminder_trigger(stripped):
        return None

    parser = get_reminder_parser()
    match = parser.find(stripped) if parser is not None else None
    list_type = ListType.tasks
    recurrence = None
    if match is not None:
        fact = match.fact
        if fact.list_type is not None:
            list_type = fact.list_type
        recurrence = fact.recurrence

    if "купить" in stripped.lower() or "купи" in stripped.lower():
        list_type = ListType.shopping

    due_at, remainder = extract_datetime(stripped, timezone)
    title = _clean_title(remainder) if remainder else _clean_title(stripped)

    for noise in (
        "каждый день",
        "по будням",
        "каждую неделю",
        "каждый месяц",
        "в ",
    ):
        title = title.replace(noise, " ")
    title = re.sub(r"\s+", " ", title).strip(" ,.-")

    if not title:
        return None

    is_recurring = recurrence is not None
    notifications_enabled = due_at is not None

    return ParsedReminder(
        list_type=list_type,
        title=title,
        due_at=due_at,
        notifications_enabled=notifications_enabled,
        is_recurring=is_recurring,
        recurrence=recurrence,
        raw_text=stripped,
    )


def recurrence_to_rrule(parsed: ParsedReminder) -> str | None:
    if parsed.recurrence is None:
        return None
    return RRULE_BY_PRESET.get(parsed.recurrence)
