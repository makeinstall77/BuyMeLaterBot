"""DataUpdateCoordinator for BuyMeLater."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import BuyMeLaterApiClient, BuyMeLaterApiError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class BuyMeLaterList:
    list_id: str
    scope_id: str
    scope_title: str
    scope_type: str
    list_type: str
    name: str
    telegram_chat_id: int
    ha_user_id: str | None = None


class BuyMeLaterCoordinator(DataUpdateCoordinator[dict[str, list[dict[str, Any]]]]):
    def __init__(
        self,
        hass: HomeAssistant,
        client: BuyMeLaterApiClient,
        lists: list[BuyMeLaterList],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client
        self.lists = lists
        self.linked_users: list[dict[str, Any]] = []

    async def _async_update_data(self) -> dict[str, list[dict[str, Any]]]:
        try:
            self.linked_users = await self.client.async_get_linked_users()
        except BuyMeLaterApiError as err:
            raise UpdateFailed(str(err)) from err

        data: dict[str, list[dict[str, Any]]] = {}
        for lst in self.lists:
            try:
                data[lst.list_id] = await self.client.async_get_items(lst.list_id)
            except BuyMeLaterApiError as err:
                raise UpdateFailed(str(err)) from err
        return data
