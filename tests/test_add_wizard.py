from uuid import uuid4

from bot.state import (
    clear_add_wizard,
    get_pending_add,
    pop_pending_add_recur,
    set_pending_add,
    set_pending_add_recur,
)
from core.models import ListType
from core.schemas import RecurrencePreset


def test_pending_add_roundtrip() -> None:
    set_pending_add(42, ListType.tasks)
    assert get_pending_add(42) == ListType.tasks
    clear_add_wizard(42)
    assert get_pending_add(42) is None


def test_pending_add_recur_once() -> None:
    item_id = uuid4()
    set_pending_add_recur(7, item_id, None)
    pending = pop_pending_add_recur(7)
    assert pending == (item_id, None)


def test_pending_add_recur_daily() -> None:
    item_id = uuid4()
    set_pending_add_recur(8, item_id, RecurrencePreset.daily)
    pending = pop_pending_add_recur(8)
    assert pending is not None
    assert pending[0] == item_id
    assert pending[1] == RecurrencePreset.daily
