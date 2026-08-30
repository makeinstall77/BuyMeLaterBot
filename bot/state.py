from uuid import UUID

_pending_parsed: dict[int, dict] = {}
_pending_due_edit: dict[int, UUID] = {}


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
