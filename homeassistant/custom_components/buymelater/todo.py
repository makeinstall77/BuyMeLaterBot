"""BuyMeLater todo entities."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BuyMeLaterCoordinator, BuyMeLaterList


def _item_description(item: dict[str, Any]) -> str | None:
    parts: list[str] = []
    if item.get("is_recurring") and item.get("rrule"):
        parts.append(f"🔁 {item['rrule']}")
    if item.get("notifications_enabled"):
        parts.append("🔔 уведомления вкл")
    return " | ".join(parts) if parts else None


def _parse_due(item: dict[str, Any]) -> datetime | None:
    due = item.get("due_at")
    if not due:
        return None
    return datetime.fromisoformat(due.replace("Z", "+00:00"))


def _api_item_to_todo(item: dict[str, Any]) -> TodoItem:
    status = (
        TodoItemStatus.COMPLETED
        if item.get("status") == "completed"
        else TodoItemStatus.NEEDS_ACTION
    )
    return TodoItem(
        uid=str(item["id"]),
        summary=item["title"],
        status=status,
        due=_parse_due(item),
        description=_item_description(item),
    )


class BuyMeLaterTodoList(CoordinatorEntity[BuyMeLaterCoordinator], TodoListEntity):
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.SET_DUE_DATETIME_ON_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
    )

    def __init__(self, coordinator: BuyMeLaterCoordinator, lst: BuyMeLaterList) -> None:
        super().__init__(coordinator)
        self._list = lst
        self._attr_unique_id = f"{lst.list_id}"
        self._attr_name = f"{lst.scope_title} — {lst.name}"
        self._attr_icon = "mdi:cart" if lst.list_type == "shopping" else "mdi:clipboard-list"

    @property
    def todo_items(self) -> list[TodoItem] | None:
        items = self.coordinator.data.get(self._list.list_id)
        if items is None:
            return None
        return [_api_item_to_todo(item) for item in items]

    async def async_create_todo_item(self, item: TodoItem) -> None:
        payload: dict[str, Any] = {"title": item.summary or "Без названия"}
        if item.due:
            payload["due_at"] = item.due.isoformat()
            payload["notifications_enabled"] = True
        if item.description:
            payload["description"] = item.description
        await self.coordinator.client.async_create_item(self._list.list_id, payload)
        await self.coordinator.async_request_refresh()

    async def async_update_todo_item(self, item: TodoItem) -> None:
        payload: dict[str, Any] = {}
        if item.summary is not None:
            payload["title"] = item.summary
        if item.description is not None:
            payload["description"] = item.description
        if item.due is not None:
            payload["due_at"] = item.due.isoformat()
        if item.status == TodoItemStatus.COMPLETED:
            payload["status"] = "completed"
        elif item.status == TodoItemStatus.NEEDS_ACTION:
            payload["status"] = "active"
        await self.coordinator.client.async_update_item(item.uid or "", payload)
        await self.coordinator.async_request_refresh()

    async def async_delete_todo_items(self, uids: list[str]) -> None:
        for uid in uids:
            await self.coordinator.client.async_delete_item(uid)
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: BuyMeLaterCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        BuyMeLaterTodoList(coordinator, lst) for lst in coordinator.lists
    )
