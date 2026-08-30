"""BuyMeLater integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BuyMeLaterApiClient
from .const import CONF_API_TOKEN, CONF_URL, DATA_COORDINATOR, DOMAIN
from .coordinator import BuyMeLaterCoordinator, BuyMeLaterList

PLATFORMS = [Platform.TODO]


async def _discover_lists(client: BuyMeLaterApiClient) -> list[BuyMeLaterList]:
    linked = await client.async_get_linked_users()
    linked_by_tg = {u["telegram_user_id"]: u["ha_user_id"] for u in linked}

    lists: list[BuyMeLaterList] = []
    scopes = await client.async_get_scopes()
    for scope in scopes:
        if scope["scope_type"] == "personal":
            ha_user_id = linked_by_tg.get(scope["telegram_chat_id"])
            if ha_user_id is None:
                continue
        else:
            ha_user_id = None

        scope_lists = await client.async_get_lists(scope["id"])
        for lst in scope_lists:
            lists.append(
                BuyMeLaterList(
                    list_id=lst["id"],
                    scope_id=scope["id"],
                    scope_title=scope["title"],
                    scope_type=scope["scope_type"],
                    list_type=lst["list_type"],
                    name=lst["name"],
                    telegram_chat_id=scope["telegram_chat_id"],
                    ha_user_id=ha_user_id,
                )
            )
    return lists


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = async_get_clientsession(hass)
    client = BuyMeLaterApiClient(session, entry.data[CONF_URL], entry.data[CONF_API_TOKEN])
    lists = await _discover_lists(client)
    coordinator = BuyMeLaterCoordinator(hass, client, lists)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        "client": client,
        "entry": entry,
        "client_session": session,
    }

    from .ws_listener import async_start_ws_listener

    stop_listener = async_start_ws_listener(hass, entry.entry_id)
    hass.data[DOMAIN][entry.entry_id]["stop_listener"] = stop_listener

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _register_panel(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry_data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if entry_data and (stop := entry_data.get("stop_listener")):
        stop()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def _register_panel(hass: HomeAssistant) -> None:
    if hass.data.get(DOMAIN, {}).get("panel_registered"):
        return

    from pathlib import Path

    from homeassistant.components import panel_custom
    from homeassistant.components.http import StaticPathConfig

    frontend_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/buymelater-panel", str(frontend_dir), False)]
    )
    panel_custom.async_register_panel(
        hass,
        frontend_url_path="buymelater",
        module_url="/buymelater-panel/buymelater-panel.js",
        panel_icon="mdi:cart-check",
        panel_title="BuyMeLater",
        require_admin=False,
    )
    hass.data.setdefault(DOMAIN, {})["panel_registered"] = True
