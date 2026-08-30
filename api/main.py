from uuid import UUID

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import verify_api_token
from core.crud import (
    create_item,
    delete_item,
    get_item,
    get_list,
    get_lists_for_scope,
    list_items,
    list_scopes,
    update_item,
)
from core.db import get_session
from core.models import ItemStatus, ScopeType
from core.schemas import ItemCreate, ItemRead, ItemUpdate, ListRead, ScopeRead

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
    return ItemRead.model_validate(item)


@router.delete("/items/{item_id}", status_code=204)
async def api_delete_item(
    item_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> None:
    item = await get_item(session, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    await delete_item(session, item)
    await session.commit()


app.include_router(router)
