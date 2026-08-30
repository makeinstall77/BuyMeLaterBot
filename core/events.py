from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.models import Item

WS_EVENTS_KEY = "ws_events"


def queue_ws_event(session: AsyncSession, event: str, payload: dict[str, Any]) -> None:
    session.info.setdefault(WS_EVENTS_KEY, []).append((event, payload))


from core.recurrence import format_rrule_label


def item_ws_payload(item: Item, event: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(item.id),
        "list_id": str(item.list_id),
        "title": item.title,
        "status": item.status.value if item.status else None,
        "due_at": item.due_at.isoformat() if item.due_at else None,
        "is_recurring": item.is_recurring,
        "rrule": item.rrule,
        "recurrence_label": format_rrule_label(item.rrule, item.is_recurring),
        "notifications_enabled": item.notifications_enabled,
    }
    if item.list is not None:
        payload["list_type"] = item.list.list_type.value
        payload["scope_id"] = str(item.list.scope_id)
    if event:
        payload["event"] = event
    return payload
