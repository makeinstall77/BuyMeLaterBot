"""REST client for BuyMeLaterBot API."""

from __future__ import annotations

from typing import Any

import aiohttp

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10, sock_connect=5)


class BuyMeLaterApiError(Exception):
    """API request failed."""


class BuyMeLaterApiClient:
    def __init__(self, session: aiohttp.ClientSession, base_url: str, api_token: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_token}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self._base_url}{path}"
        kwargs.setdefault("timeout", REQUEST_TIMEOUT)
        async with self._session.request(method, url, headers=self._headers, **kwargs) as resp:
            if resp.status == 401:
                raise BuyMeLaterApiError("invalid_auth")
            if resp.status >= 400:
                text = await resp.text()
                raise BuyMeLaterApiError(f"HTTP {resp.status}: {text}")
            if resp.status == 204:
                return None
            return await resp.json()

    async def async_get_health(self) -> dict[str, str]:
        root = self._base_url.split("/api/v1")[0] if "/api/v1" in self._base_url else self._base_url
        async with self._session.get(f"{root}/health", timeout=REQUEST_TIMEOUT) as resp:
            if resp.status >= 400:
                raise BuyMeLaterApiError("cannot_connect")
            return await resp.json()

    async def async_get_scopes(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/v1/scopes")

    async def async_get_lists(self, scope_id: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"/api/v1/scopes/{scope_id}/lists")

    async def async_get_items(self, list_id: str) -> list[dict[str, Any]]:
        return await self._request("GET", f"/api/v1/lists/{list_id}/items")

    async def async_create_item(self, list_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", f"/api/v1/lists/{list_id}/items", json=payload)

    async def async_update_item(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PATCH", f"/api/v1/items/{item_id}", json=payload)

    async def async_delete_item(self, item_id: str) -> None:
        await self._request("DELETE", f"/api/v1/items/{item_id}")

    async def async_request_link_code(self, ha_user_id: str) -> dict[str, Any]:
        return await self._request("POST", "/api/v1/link/request", json={"ha_user_id": ha_user_id})

    async def async_get_linked_users(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/api/v1/users/linked")
