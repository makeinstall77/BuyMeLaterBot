"""Config flow for BuyMeLater."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import BuyMeLaterApiClient, BuyMeLaterApiError
from .const import CONF_API_TOKEN, CONF_URL, DOMAIN


def _normalize_url(url: str) -> str:
    return url.rstrip("/")


async def _validate_connection(hass: HomeAssistant, url: str, api_token: str) -> None:
    session = async_get_clientsession(hass)
    client = BuyMeLaterApiClient(session, _normalize_url(url), api_token)
    await client.async_get_scopes()


class BuyMeLaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = _normalize_url(user_input[CONF_URL])
            api_token = user_input[CONF_API_TOKEN]
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            try:
                await _validate_connection(self.hass, url, api_token)
            except BuyMeLaterApiError as err:
                if str(err) == "invalid_auth":
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "cannot_connect"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="BuyMeLater",
                    data={CONF_URL: url, CONF_API_TOKEN: api_token},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default="http://buymelater.lan:8080"): str,
                    vol.Required(CONF_API_TOKEN): str,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return BuyMeLaterOptionsFlow(config_entry)


class BuyMeLaterOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self.async_step_link()

    async def async_step_link(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        session = async_get_clientsession(self.hass)
        client = BuyMeLaterApiClient(
            session,
            self.config_entry.data[CONF_URL],
            self.config_entry.data[CONF_API_TOKEN],
        )
        ha_user_id = self.context.get("user_id") or ""
        try:
            result = await client.async_request_link_code(ha_user_id)
        except BuyMeLaterApiError:
            return self.async_abort(reason="cannot_connect")

        code = result["code"]
        return self.async_show_form(
            step_id="link",
            description_placeholders={"code": code},
        )
