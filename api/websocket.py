import json
import logging
from typing import Any

from fastapi import WebSocket

from core.schemas import ItemRead

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, event: str, data: dict[str, Any]) -> None:
        if not self._connections:
            return
        message = json.dumps({"event": event, "data": data}, default=str)
        dead: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = ConnectionManager()


async def broadcast_item_event(event: str, item) -> None:
    payload = ItemRead.model_validate(item).model_dump(mode="json")
    payload["scope_id"] = str(item.list.scope_id)
    payload["list_type"] = item.list.list_type.value
    await ws_manager.broadcast(event, payload)
