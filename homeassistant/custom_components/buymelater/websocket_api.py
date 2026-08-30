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
    item = await coordinator.client.async_create_item(lst.list_id, payload)
    await coordinator.async_request_refresh()
    connection.send_result(msg["id"], item)


@websocket_api.websocket_command(
    {
        vol.Required("type"): "buymelater/update_item",
        vol.Required("item_id"): str,
        vol.Optional("title"): str,
        vol.Optional("status"): str,
        vol.Optional("due_at"): vol.Any(str, None),
        vol.Optional("notifications_enabled"): bool,
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
        for key in ("title", "status", "due_at", "notifications_enabled")
        if key in msg
    }
    item = await coordinator.client.async_update_item(msg["item_id"], payload)
    await coordinator.async_request_refresh()
    connection.send_result(msg["id"], item)


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
    await coordinator.async_request_refresh()
    connection.send_result(msg["id"])


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
