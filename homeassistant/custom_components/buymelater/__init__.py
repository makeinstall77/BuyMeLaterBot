"""BuyMeLater integration for Home Assistant."""

from __future__ import annotations

import aiohttp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, Platform
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BuyMeLaterApiClient, BuyMeLaterApiError
from .const import CONF_API_TOKEN, CONF_URL, DATA_COORDINATOR, DOMAIN
from .coordinator import BuyMeLaterCoordinator, BuyMeLaterList

PLATFORMS = [Platform.TODO]
FRONTEND_VERSION = "0.1.5"


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
    try:
        lists = await _discover_lists(client)
    except (BuyMeLaterApiError, aiohttp.ClientError, TimeoutError) as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = BuyMeLaterCoordinator(hass, client, lists)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        "client": client,
        "entry": entry,
    }

    from .websocket_api import async_setup_ws
    from .ws_listener import async_start_ws_listener

    if not hass.data[DOMAIN].get("ws_registered"):
        async_setup_ws(hass)
        hass.data[DOMAIN]["ws_registered"] = True
    stop_listener = async_start_ws_listener(hass, entry.entry_id)
    hass.data[DOMAIN][entry.entry_id]["stop_listener"] = stop_listener

    @callback
    def _refresh_on_event(_event: Event) -> None:
        hass.async_create_task(coordinator.async_request_refresh())

    hass.data[DOMAIN][entry.entry_id]["unsub_bus"] = hass.bus.async_listen(
        "buymelater_event", _refresh_on_event
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _schedule_panel(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    entry_data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if entry_data:
        if stop := entry_data.get("stop_listener"):
            stop()
        if unsub := entry_data.get("unsub_bus"):
            unsub()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


def _schedule_panel(hass: HomeAssistant) -> None:
    if hass.data.get(DOMAIN, {}).get("panel_scheduled"):
        return
    hass.data.setdefault(DOMAIN, {})["panel_scheduled"] = True

    async def _run(_event: Event | None = None) -> None:
        await _register_panel(hass)

    if hass.state is CoreState.running:
        hass.async_create_task(_run())
        return
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _run)


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
    try:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, f"/buymelater-panel/buymelater-card.js?v={FRONTEND_VERSION}")
    except Exception:
        pass
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path="buymelater",
        webcomponent_name="buymelater-panel",
        sidebar_title="BuyMeLater",
        sidebar_icon="mdi:cart-check",
        module_url=f"/buymelater-panel/buymelater-panel.js?v={FRONTEND_VERSION}",
        require_admin=False,
    )
    hass.data.setdefault(DOMAIN, {})["panel_registered"] = True
