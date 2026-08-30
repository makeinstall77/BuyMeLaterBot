from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import verify_api_token
from api.websocket import broadcast_item_event, ws_manager
from core.config import settings
from core.crud import (
    create_item,
    delete_item,
    get_item,
    get_list,
    get_lists_for_scope,
    list_items,
    list_linked_users,
    list_scopes,
    update_item,
)
from core.db import get_session
from core.link import create_link_code
from core.models import ItemStatus, ScopeType
from core.schemas import (
    ItemCreate,
    ItemRead,
    ItemUpdate,
    LinkRequestCreate,
    LinkRequestRead,
    LinkedUserRead,
    ListRead,
    ScopeRead,
)

app = FastAPI(title="BuyMeLaterBot", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


router = APIRouter(prefix="/api/v1", tags=["buymelater"], dependencies=[Depends(verify_api_token)])


@router.get("/scopes", response_model=list[ScopeRead])
async def api_list_scopes(
    scope_type: ScopeType | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[ScopeRead]:
    scopes = await list_scopes(session, scope_type=scope_type)
    return [ScopeRead.model_validate(s) for s in scopes]


@router.get("/scopes/{scope_id}/lists", response_model=list[ListRead])
async def api_scope_lists(
    scope_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> list[ListRead]:
    lists = await get_lists_for_scope(session, scope_id)
    return [ListRead.model_validate(lst) for lst in lists]


@router.get("/lists/{list_id}/items", response_model=list[ItemRead])
async def api_list_items(
    list_id: UUID,
    status: ItemStatus | None = Query(default=ItemStatus.active),
    session: AsyncSession = Depends(get_session),
) -> list[ItemRead]:
    db_list = await get_list(session, list_id)
    if db_list is None:
        raise HTTPException(status_code=404, detail="List not found")
    items = await list_items(session, list_id, status=status)
    return [ItemRead.model_validate(item) for item in items]


@router.post("/lists/{list_id}/items", response_model=ItemRead, status_code=201)
async def api_create_item(
    list_id: UUID,
    payload: ItemCreate,
    session: AsyncSession = Depends(get_session),
) -> ItemRead:
    db_list = await get_list(session, list_id)
    if db_list is None:
        raise HTTPException(status_code=404, detail="List not found")
    item = await create_item(session, list_id, payload)
    await session.commit()
    item = await get_item(session, item.id)
    if item is not None:
        await broadcast_item_event("item_created", item)
    return ItemRead.model_validate(item)


@router.patch("/items/{item_id}", response_model=ItemRead)
async def api_update_item(
    item_id: UUID,
    payload: ItemUpdate,
    session: AsyncSession = Depends(get_session),
) -> ItemRead:
    item = await get_item(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    item = await update_item(session, item, payload)
    await session.commit()
    item = await get_item(session, item_id)
    if item is not None:
        await broadcast_item_event("item_updated", item)
    return ItemRead.model_validate(item)


@router.delete("/items/{item_id}", status_code=204)
async def api_delete_item(
    item_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    item = await get_item(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    list_type = item.list.list_type.value
    scope_id = str(item.list.scope_id)
    item_id = item.id
    await delete_item(session, item)
    await session.commit()
    await ws_manager.broadcast(
        "item_deleted",
        {"id": str(item_id), "list_type": list_type, "scope_id": scope_id},
    )


@router.post("/link/request", response_model=LinkRequestRead)
async def api_link_request(payload: LinkRequestCreate) -> LinkRequestRead:
    from datetime import UTC, datetime

    req = create_link_code(payload.ha_user_id)
    ttl = max(1, int((req.expires_at - datetime.now(UTC)).total_seconds()))
    return LinkRequestRead(code=req.code, expires_in=ttl)


@router.get("/users/linked", response_model=list[LinkedUserRead])
async def api_linked_users(
    session: AsyncSession = Depends(get_session),
) -> list[LinkedUserRead]:
    users = await list_linked_users(session)
    return [LinkedUserRead.model_validate(u) for u in users]


@app.websocket("/ws")
async def websocket_events(websocket: WebSocket, token: str = Query(...)) -> None:
    if token != settings.api_token:
        await websocket.close(code=1008, reason="Invalid token")
        return
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


app.include_router(router)
