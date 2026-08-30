"""WebSocket commands for the BuyMeLater panel and card."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import BuyMeLaterCoordinator


def _coordinators(hass: HomeAssistant) -> list[BuyMeLaterCoordinator]:
    return [
        data[DATA_COORDINATOR]
        for data in hass.data.get(DOMAIN, {}).values()
        if isinstance(data, dict) and DATA_COORDINATOR in data
    ]


def _serialize_list(coordinator: BuyMeLaterCoordinator, lst) -> dict[str, Any]:
    return {
        "list_id": lst.list_id,
        "scope_id": lst.scope_id,
        "scope_title": lst.scope_title,
        "scope_type": lst.scope_type,
        "list_type": lst.list_type,
        "name": lst.name,
        "ha_user_id": lst.ha_user_id,
        "items": coordinator.data.get(lst.list_id, []) if coordinator.data else [],
    }


def _patch_item(coordinator: BuyMeLaterCoordinator, item: dict[str, Any]) -> None:
    if coordinator.data is None:
        coordinator.data = {}
    list_id = str(item.get("list_id") or "")
    if not list_id:
        return
    items = list(coordinator.data.get(list_id, []))
    iid = str(item.get("id"))
    replaced = False
    for idx, existing in enumerate(items):
        if str(existing.get("id")) == iid:
            items[idx] = item
            replaced = True
            break
    if not replaced:
        items.append(item)
    coordinator.data[list_id] = items


def _remove_item(coordinator: BuyMeLaterCoordinator, item_id: str) -> None:
    if not coordinator.data:
        return
    iid = str(item_id)
    for list_id, items in list(coordinator.data.items()):
        coordinator.data[list_id] = [item for item in items if str(item.get("id")) != iid]


def _notify_ui(hass: HomeAssistant, payload: dict[str, Any]) -> None:
    hass.bus.async_fire("buymelater_event", payload)


@callback
def async_setup_ws(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_overview)
    websocket_api.async_register_command(hass, ws_create_item)
    websocket_api.async_register_command(hass, ws_update_item)
    websocket_api.async_register_command(hass, ws_delete_item)


@websocket_api.websocket_command({vol.Required("type"): "buymelater/overview"})
@websocket_api.async_response
async def ws_overview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    lists: list[dict[str, Any]] = []
    for coordinator in _coordinators(hass):
        for lst in coordinator.lists:
            lists.append(_serialize_list(coordinator, lst))
    connection.send_result(msg["id"], {"lists": lists, "user_id": connection.user.id})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "buymelater/create_item",
        vol.Required("list_id"): str,
        vol.Required("title"): str,
        vol.Optional("due_at"): vol.Any(str, None),
        vol.Optional("notifications_enabled", default=False): bool,
        vol.Optional("is_recurring"): bool,
        vol.Optional("rrule"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_create_item(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    coordinator, lst = _find_list(hass, msg["list_id"])
    if coordinator is None or lst is None:
        connection.send_error(msg["id"], "not_found", "List not found")
        return
    payload: dict[str, Any] = {
        "title": msg["title"].strip(),
        "notifications_enabled": msg.get("notifications_enabled", False),
    }
    if msg.get("due_at"):
        payload["due_at"] = msg["due_at"]
        payload["notifications_enabled"] = True
    if "is_recurring" in msg:
        payload["is_recurring"] = msg["is_recurring"]
    if "rrule" in msg:
        payload["rrule"] = msg["rrule"]
    item = await coordinator.client.async_create_item(lst.list_id, payload)
    _patch_item(coordinator, item)
    _notify_ui(hass, {"event": "item_created", **item})
    connection.send_result(msg["id"], item)
    hass.async_create_task(coordinator.async_refresh())


@websocket_api.websocket_command(
    {
        vol.Required("type"): "buymelater/update_item",
        vol.Required("item_id"): str,
        vol.Optional("title"): str,
        vol.Optional("status"): str,
        vol.Optional("due_at"): vol.Any(str, None),
        vol.Optional("notifications_enabled"): bool,
        vol.Optional("is_recurring"): bool,
        vol.Optional("rrule"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_update_item(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    coordinator = _find_item_coordinator(hass, msg["item_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Item not found")
        return
    payload = {
        key: msg[key]
        for key in ("title", "status", "due_at", "notifications_enabled", "is_recurring", "rrule")
        if key in msg
    }
    item = await coordinator.client.async_update_item(msg["item_id"], payload)
    _patch_item(coordinator, item)
    _notify_ui(hass, {"event": "item_updated", **item})
    connection.send_result(msg["id"], item)
    hass.async_create_task(coordinator.async_refresh())


@websocket_api.websocket_command(
    {
        vol.Required("type"): "buymelater/delete_item",
        vol.Required("item_id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_item(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    coordinator = _find_item_coordinator(hass, msg["item_id"])
    if coordinator is None:
        connection.send_error(msg["id"], "not_found", "Item not found")
        return
    await coordinator.client.async_delete_item(msg["item_id"])
    _remove_item(coordinator, msg["item_id"])
    _notify_ui(hass, {"event": "item_deleted", "id": msg["item_id"]})
    connection.send_result(msg["id"])
    hass.async_create_task(coordinator.async_refresh())


def _find_list(hass: HomeAssistant, list_id: str):
    for coordinator in _coordinators(hass):
        for lst in coordinator.lists:
            if lst.list_id == list_id:
                return coordinator, lst
    return None, None


def _find_item_coordinator(hass: HomeAssistant, item_id: str) -> BuyMeLaterCoordinator | None:
    for coordinator in _coordinators(hass):
        if not coordinator.data:
            continue
        for items in coordinator.data.values():
            if any(str(item.get("id")) == item_id for item in items):
                return coordinator
    return None
