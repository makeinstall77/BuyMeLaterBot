from datetime import UTC, datetime
from uuid import UUID

from aiogram.types import Chat, User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.events import item_ws_payload, queue_ws_event
from core.models import Item, ItemStatus, List, ListType, Scope, ScopeType, TelegramUser
from core.recurrence import initial_next_notify, next_notify_after
from core.schemas import ItemCreate, ItemUpdate


async def get_or_create_user(session: AsyncSession, user: User, timezone: str) -> TelegramUser:
    result = await session.execute(
        select(TelegramUser).where(TelegramUser.telegram_user_id == user.id)
    )
    db_user = result.scalar_one_or_none()
    display_name = user.full_name or user.username or str(user.id)
    if db_user is None:
        db_user = TelegramUser(
            telegram_user_id=user.id,
            username=user.username,
            display_name=display_name,
            timezone=timezone,
        )
        session.add(db_user)
        await session.flush()
    else:
        db_user.username = user.username
        db_user.display_name = display_name
    return db_user


async def update_user_timezone(session: AsyncSession, user: TelegramUser, timezone: str) -> TelegramUser:
    user.timezone = timezone
    await session.flush()
    return user


async def update_scope_timezone(session: AsyncSession, scope: Scope, timezone: str) -> Scope:
    scope.timezone = timezone
    await session.flush()
    return scope


async def link_ha_user(session: AsyncSession, user: TelegramUser, ha_user_id: str) -> TelegramUser:
    user.ha_user_id = ha_user_id
    await session.flush()
    return user


async def list_linked_users(session: AsyncSession) -> list[TelegramUser]:
    result = await session.execute(
        select(TelegramUser)
        .where(TelegramUser.ha_user_id.is_not(None))
        .order_by(TelegramUser.display_name)
    )
    return list(result.scalars().all())


async def get_user_by_telegram_id(session: AsyncSession, telegram_user_id: int) -> TelegramUser | None:
    result = await session.execute(
        select(TelegramUser).where(TelegramUser.telegram_user_id == telegram_user_id)
    )
    return result.scalar_one_or_none()


async def _create_default_lists(session: AsyncSession, scope: Scope) -> None:
    session.add_all(
        [
            List(scope_id=scope.id, list_type=ListType.shopping, name="Покупки"),
            List(scope_id=scope.id, list_type=ListType.tasks, name="Дела"),
        ]
    )


async def get_or_create_scope(
    session: AsyncSession,
    chat: Chat,
    *,
    default_timezone: str,
    title: str | None = None,
) -> Scope:
    result = await session.execute(select(Scope).where(Scope.telegram_chat_id == chat.id))
    scope = result.scalar_one_or_none()
    if scope is not None:
        return scope

    if chat.type == "private":
        scope_type = ScopeType.personal
        scope_title = title or "Личный"
    else:
        scope_type = ScopeType.group
        scope_title = title or chat.title or "Группа"

    scope = Scope(
        scope_type=scope_type,
        telegram_chat_id=chat.id,
        title=scope_title,
        timezone=default_timezone,
    )
    session.add(scope)
    await session.flush()
    await _create_default_lists(session, scope)
    return scope


async def get_scope_by_chat_id(session: AsyncSession, chat_id: int) -> Scope | None:
    result = await session.execute(select(Scope).where(Scope.telegram_chat_id == chat_id))
    return result.scalar_one_or_none()


async def list_scopes(
    session: AsyncSession, *, scope_type: ScopeType | None = None
) -> list[Scope]:
    stmt = select(Scope).order_by(Scope.title)
    if scope_type is not None:
        stmt = stmt.where(Scope.scope_type == scope_type)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_list_by_type(
    session: AsyncSession, scope_id: UUID, list_type: ListType
) -> List | None:
    result = await session.execute(
        select(List).where(List.scope_id == scope_id, List.list_type == list_type)
    )
    return result.scalar_one_or_none()


async def get_lists_for_scope(session: AsyncSession, scope_id: UUID) -> list[List]:
    result = await session.execute(
        select(List).where(List.scope_id == scope_id).order_by(List.list_type)
    )
    return list(result.scalars().all())


async def get_list(session: AsyncSession, list_id: UUID) -> List | None:
    result = await session.execute(select(List).where(List.id == list_id))
    return result.scalar_one_or_none()


async def list_items(
    session: AsyncSession,
    list_id: UUID,
    *,
    status: ItemStatus | None = ItemStatus.active,
) -> list[Item]:
    stmt = select(Item).where(Item.list_id == list_id).order_by(Item.created_at.desc())
    if status is not None:
        stmt = stmt.where(Item.status == status)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_item(session: AsyncSession, item_id: UUID) -> Item | None:
    result = await session.execute(
        select(Item)
        .options(selectinload(Item.list).selectinload(List.scope))
        .where(Item.id == item_id)
    )
    return result.scalar_one_or_none()


async def create_item(session: AsyncSession, list_id: UUID, data: ItemCreate) -> Item:
    next_notify_at = None
    if data.notifications_enabled and data.due_at:
        if data.is_recurring and data.rrule:
            next_notify_at = initial_next_notify(data.due_at, data.rrule)
        else:
            next_notify_at = data.due_at
    item = Item(
        list_id=list_id,
        title=data.title.strip(),
        description=data.description,
        created_by_id=data.created_by_id,
        due_at=data.due_at,
        is_recurring=data.is_recurring,
        rrule=data.rrule,
        notifications_enabled=data.notifications_enabled,
        next_notify_at=next_notify_at,
    )
    session.add(item)
    await session.flush()
    loaded = await get_item(session, item.id)
    if loaded is not None:
        queue_ws_event(session, "item_created", item_ws_payload(loaded))
        return loaded
    return item


async def update_item(session: AsyncSession, item: Item, data: ItemUpdate) -> Item:
    fields = data.model_dump(exclude_unset=True)
    for key, value in fields.items():
        setattr(item, key, value)

    if data.status == ItemStatus.completed and item.completed_at is None:
        item.completed_at = datetime.now(UTC)
        item.notifications_enabled = False
        item.next_notify_at = None
    elif data.status == ItemStatus.active:
        item.completed_at = None

    if data.notifications_enabled is False:
        item.next_notify_at = None
    elif data.notifications_enabled and item.due_at:
        item.next_notify_at = item.due_at

    if "due_at" in fields and data.notifications_enabled is None:
        if item.due_at is None:
            item.next_notify_at = None
        elif item.notifications_enabled:
            item.next_notify_at = item.due_at

    await session.flush()
    queue_ws_event(session, "item_updated", item_ws_payload(item))
    return item


async def delete_item(session: AsyncSession, item: Item) -> None:
    queue_ws_event(
        session,
        "item_deleted",
        {
            "id": str(item.id),
            "list_id": str(item.list_id),
            "list_type": item.list.list_type.value if item.list else None,
            "scope_id": str(item.list.scope_id) if item.list else None,
        },
    )
    await session.delete(item)


async def complete_item(session: AsyncSession, item: Item) -> Item:
    return await update_item(
        session,
        item,
        ItemUpdate(status=ItemStatus.completed, notifications_enabled=False, next_notify_at=None),
    )


async def get_due_notifications(session: AsyncSession, now: datetime) -> list[Item]:
    result = await session.execute(
        select(Item)
        .options(selectinload(Item.list).selectinload(List.scope))
        .where(
            Item.status == ItemStatus.active,
            Item.notifications_enabled.is_(True),
            Item.next_notify_at.is_not(None),
            Item.next_notify_at <= now,
        )
    )
    return list(result.scalars().all())


async def mark_notified(session: AsyncSession, item: Item, *, now: datetime) -> Item:
    item.last_notified_at = now
    if item.is_recurring and item.rrule and item.due_at:
        nxt = next_notify_after(item.rrule, item.due_at, now)
        if nxt is None:
            item.notifications_enabled = False
            item.next_notify_at = None
        else:
            item.next_notify_at = nxt
    else:
        item.notifications_enabled = False
        item.next_notify_at = None
    await session.flush()
    return item
