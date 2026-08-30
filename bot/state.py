from datetime import date
from uuid import UUID

from core.models import ListType
from core.schemas import RecurrencePreset

_pending_parsed: dict[int, dict] = {}
_pending_due_edit: dict[int, UUID] = {}
_pending_add: dict[int, ListType] = {}
_wizard: dict[int, dict] = {}


def store_pending_parsed(user_id: int, data: dict) -> None:
    _pending_parsed[user_id] = data


def pop_pending_parsed(user_id: int) -> dict | None:
    return _pending_parsed.pop(user_id, None)


def set_pending_due_edit(user_id: int, item_id: UUID) -> None:
    _pending_due_edit[user_id] = item_id


def pop_pending_due_edit(user_id: int) -> UUID | None:
    return _pending_due_edit.pop(user_id, None)


def get_pending_due_edit(user_id: int) -> UUID | None:
    return _pending_due_edit.get(user_id)


def set_pending_add(user_id: int, list_type: ListType) -> None:
    _pending_add[user_id] = list_type


def pop_pending_add(user_id: int) -> ListType | None:
    return _pending_add.pop(user_id, None)


def get_pending_add(user_id: int) -> ListType | None:
    return _pending_add.get(user_id)


def update_wizard(user_id: int, **fields) -> dict:
    data = _wizard.get(user_id, {})
    data.update(fields)
    _wizard[user_id] = data
    return data


def get_wizard(user_id: int) -> dict | None:
    return _wizard.get(user_id)


def pop_wizard(user_id: int) -> dict | None:
    return _wizard.pop(user_id, None)


def set_pending_add_recur(
    user_id: int,
    item_id: UUID,
    preset: RecurrencePreset | None,
    *,
    byday: str | None = None,
    monthday: int | None = None,
    once_date: date | None = None,
    awaiting: str | None = None,
) -> None:
    update_wizard(
        user_id,
        item_id=item_id,
        preset=preset,
        byday=byday,
        monthday=monthday,
        once_date=once_date,
        awaiting=awaiting,
    )


def pop_pending_add_recur(user_id: int) -> tuple[UUID, RecurrencePreset | None] | None:
    data = pop_wizard(user_id)
    if data is None or "item_id" not in data:
        return None
    return data["item_id"], data.get("preset")


def clear_add_wizard(user_id: int) -> None:
    _pending_add.pop(user_id, None)
    _wizard.pop(user_id, None)
    _pending_due_edit.pop(user_id, None)
