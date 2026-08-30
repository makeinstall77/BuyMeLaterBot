from yargy import Parser, rule, or_
from yargy.interpretation import fact
from yargy.pipelines import morph_pipeline
from yargy.predicates import caseless

from core.models import ListType
from core.schemas import RecurrencePreset

ReminderCommand = fact("ReminderCommand", ["list_type", "recurrence"])

TRIGGER = morph_pipeline(["напомни", "напоминание", "добавь", "не забудь"])
SHOPPING = morph_pipeline(["купить", "купи"])
RECURRENCE_DAILY = rule(caseless("каждый"), caseless("день"))
RECURRENCE_WEEKDAYS = morph_pipeline(["по будням"])
RECURRENCE_WEEKLY = rule(caseless("каждую"), caseless("неделю"))
RECURRENCE_MONTHLY = rule(caseless("каждый"), caseless("месяц"))

RECURRENCE = or_(
    RECURRENCE_DAILY.interpretation(ReminderCommand.recurrence.const(RecurrencePreset.daily)),
    RECURRENCE_WEEKDAYS.interpretation(ReminderCommand.recurrence.const(RecurrencePreset.weekdays)),
    RECURRENCE_WEEKLY.interpretation(ReminderCommand.recurrence.const(RecurrencePreset.weekly)),
    RECURRENCE_MONTHLY.interpretation(ReminderCommand.recurrence.const(RecurrencePreset.monthly)),
)

REMINDER = rule(
    TRIGGER,
    or_(
        rule(SHOPPING).interpretation(ReminderCommand.list_type.const(ListType.shopping)),
        rule().interpretation(ReminderCommand.list_type.const(ListType.tasks)),
    ).optional(),
    RECURRENCE.optional(),
).interpretation(ReminderCommand)

_reminder_parser: Parser | None = None
_parser_init_failed = False


def get_reminder_parser() -> Parser | None:
    global _reminder_parser, _parser_init_failed
    if _parser_init_failed:
        return None
    if _reminder_parser is None:
        try:
            _reminder_parser = Parser(REMINDER)
        except Exception:
            _parser_init_failed = True
            return None
    return _reminder_parser


def has_reminder_trigger(text: str) -> bool:
    normalized = text.strip().lower()
    triggers = ("напомни", "напоминание", "добавь", "не забудь", "купить", "купи")
    return any(word in normalized for word in triggers)
