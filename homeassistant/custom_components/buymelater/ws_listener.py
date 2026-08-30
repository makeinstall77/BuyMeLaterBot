"""WebSocket listener forwarding bot events to HA bus."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, Event, HomeAssistant, callback

from .const import CONF_API_TOKEN, CONF_URL, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _ws_url(base_url: str, token: str) -> str:
    root = base_url.rstrip("/")
    scheme = "wss" if root.startswith("https://") else "ws"
    host = root.removeprefix("https://").removeprefix("http://")
    return f"{scheme}://{host}/ws?token={token}"


async def _listen_forever(hass: HomeAssistant, entry_id: str) -> None:
    entry = hass.data[DOMAIN][entry_id]
    url = entry["entry"].data[CONF_URL]
    token = entry["entry"].data[CONF_API_TOKEN]
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while True:
            ws_url = _ws_url(url, token)
            try:
                async with session.ws_connect(ws_url, heartbeat=30) as ws:
                    _LOGGER.debug("Connected to BuyMeLater websocket")
                    async for msg in ws:
                        if msg.type != aiohttp.WSMsgType.TEXT:
                            continue
                        payload: dict[str, Any] = json.loads(msg.data)
                        hass.bus.async_fire("buymelater_event", payload)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                _LOGGER.debug("BuyMeLater websocket disconnected: %s", err)
                await asyncio.sleep(5)


@callback
def async_start_ws_listener(hass: HomeAssistant, entry_id: str) -> callable:
    task: asyncio.Task | None = None
    unsub: callable | None = None

    def _spawn() -> None:
        nonlocal task
        if task is None or task.done():
            task = hass.async_create_task(_listen_forever(hass, entry_id))

    def _on_started(_event: Event) -> None:
        _spawn()

    if hass.state is CoreState.running:
        _spawn()
    else:
        unsub = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _on_started)

    @callback
    def stop() -> None:
        if unsub:
            unsub()
        if task:
            task.cancel()

    return stop
